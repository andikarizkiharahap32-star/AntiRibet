"""
Command Line Interface for AutoAccount Creator
Provides CLI commands for bulk account creation and management
"""
import click
import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
import csv
import json
from datetime import datetime, timezone

from app.core.database import async_session_maker, close_db
from app.models.job import Job
from app.models.account import Account
from app.workers.tasks import create_accounts_task
from app.core.config import settings
from app.services.account_service import AccountService


@click.group()
def cli():
    """AAC - AutoAccountCreator CLI"""
    pass


async def _ensure_cli_user_id(db: AsyncSession):
    service = AccountService(db)
    user = await service.ensure_cli_user()
    return user.id


async def _run_and_close(coro):
    try:
        return await coro
    finally:
        await close_db()


@cli.command()
@click.option('--platform', type=click.Choice(['discord', 'gmail']), required=True, help='Platform to create accounts for')
@click.option('--count', type=int, required=True, help='Number of accounts to create (1-1000)')
@click.option('--proxy-provider', default='brightdata', help='Proxy provider (brightdata/smartproxy)')
@click.option('--sms-provider', default='5sim', help='SMS provider for Gmail (5sim/smsactivate)')
@click.option('--captcha-provider', default='2captcha', help='Captcha solver (2captcha/anticaptcha)')
def create(platform, count, proxy_provider, sms_provider, captcha_provider):
    """
    Create accounts in bulk
    
    Example:
        python -m app.cli create --platform discord --count 100
    """
    if count < 1 or count > 1000:
        click.echo("Error: Count must be between 1 and 1000", err=True)
        return
    
    click.echo(f"Creating {count} {platform} accounts...")
    
    async def _create():
        async with async_session_maker() as db:
            # Create/reuse system CLI user (required by non-null FK jobs.user_id)
            cli_user_id = await _ensure_cli_user_id(db)

            # Create job
            job = Job(
                id=uuid.uuid4(),
                user_id=cli_user_id,
                type=platform,
                total_count=count,
                status="pending",
                proxy_provider=proxy_provider,
                sms_provider=sms_provider,
                captcha_provider=captcha_provider
            )

            db.add(job)
            await db.commit()
            await db.refresh(job)
            
            click.echo(f"Job created: {job.id}")
            
            # Queue Celery task
            task = create_accounts_task.delay(
                job_id=str(job.id),
                platform=platform,
                total_count=count,
                proxy_provider=proxy_provider,
                sms_provider=sms_provider,
                captcha_provider=captcha_provider
            )
            
            click.echo(f"Task queued: {task.id}")
            click.echo(f"Monitor progress: http://localhost:5555/task/{task.id}")
            
            return job.id
    
    job_id = asyncio.run(_run_and_close(_create()))
    click.echo(f"\n✅ Job {job_id} created successfully!")
    click.echo(f"Check status with: python -m app.cli status --job-id {job_id}")


@cli.command()
@click.option('--job-id', required=True, help='Job ID to check status')
def status(job_id):
    """
    Check job status
    
    Example:
        python -m app.cli status --job-id <uuid>
    """
    async def _status():
        async with async_session_maker() as db:
            result = await db.execute(
                select(Job).where(Job.id == uuid.UUID(job_id))
            )
            job = result.scalar_one_or_none()
            
            if not job:
                click.echo(f"Job {job_id} not found", err=True)
                return
            
            click.echo("\n" + "="*60)
            click.echo(f"Job ID: {job.id}")
            click.echo(f"Platform: {job.type}")
            click.echo(f"Status: {job.status}")
            click.echo(f"Total Count: {job.total_count}")
            click.echo(f"Success: {job.success_count}")
            click.echo(f"Failed: {job.failed_count}")
            click.echo(f"Cancelled: {job.cancelled_count}")
            click.echo(f"Progress: {((job.success_count + job.failed_count + job.cancelled_count) / job.total_count * 100):.1f}%")
            click.echo(f"Created: {job.created_at}")
            if job.finished_at:
                click.echo(f"Finished: {job.finished_at}")
            click.echo("="*60 + "\n")
    
    asyncio.run(_run_and_close(_status()))


@cli.command()
@click.option('--platform', type=click.Choice(['discord', 'gmail', 'all']), default='all', help='Filter by platform')
@click.option('--job-id', help='Filter by job ID')
@click.option('--format', type=click.Choice(['csv', 'json']), default='csv', help='Export format')
@click.option('--output', required=True, help='Output file path')
def export(platform, job_id, format, output):
    """
    Export accounts to CSV or JSON
    
    Example:
        python -m app.cli export --platform discord --format csv --output accounts.csv
    """
    async def _export():
        async with async_session_maker() as db:
            query = select(Account).where(Account.status == "success")
            
            if platform != 'all':
                query = query.where(Account.platform == platform)
            
            if job_id:
                query = query.where(Account.job_id == uuid.UUID(job_id))
            
            query = query.order_by(Account.created_at.desc()).limit(10000)
            
            result = await db.execute(query)
            accounts = result.scalars().all()
            
            if not accounts:
                click.echo("No accounts found matching criteria", err=True)
                return
            
            # Decrypt passwords
            exported_data = []
            for account in accounts:
                try:
                    password = decrypt_password(account.password_encrypted)
                    exported_data.append({
                        "id": str(account.id),
                        "platform": account.platform,
                        "email": account.email,
                        "username": account.username,
                        "password": password,
                        "token": account.token,
                        "proxy_used": account.proxy_used,
                        "created_at": account.created_at.isoformat()
                    })
                except Exception as e:
                    click.echo(f"Warning: Failed to decrypt account {account.id}: {e}", err=True)
            
            # Export
            if format == 'csv':
                with open(output, 'w', newline='', encoding='utf-8') as f:
                    if exported_data:
                        writer = csv.DictWriter(f, fieldnames=exported_data[0].keys())
                        writer.writeheader()
                        writer.writerows(exported_data)
            else:  # json
                with open(output, 'w', encoding='utf-8') as f:
                    json.dump(exported_data, f, indent=2)
            
            click.echo(f"\n✅ Exported {len(exported_data)} accounts to {output}")
    
    asyncio.run(_run_and_close(_export()))


@cli.command()
def list_jobs():
    """
    List all jobs
    
    Example:
        python -m app.cli list-jobs
    """
    async def _list():
        async with async_session_maker() as db:
            result = await db.execute(
                select(Job).order_by(Job.created_at.desc()).limit(50)
            )
            jobs = result.scalars().all()
            
            if not jobs:
                click.echo("No jobs found")
                return
            
            click.echo("\n" + "="*100)
            click.echo(f"{'Job ID':<36} {'Platform':<10} {'Status':<12} {'Success':<8} {'Failed':<8} {'Created':<20}")
            click.echo("="*100)
            
            for job in jobs:
                click.echo(
                    f"{str(job.id):<36} "
                    f"{job.type:<10} "
                    f"{job.status:<12} "
                    f"{job.success_count:<8} "
                    f"{job.failed_count:<8} "
                    f"{job.created_at.strftime('%Y-%m-%d %H:%M:%S'):<20}"
                )
            
            click.echo("="*100 + "\n")
    
    asyncio.run(_run_and_close(_list()))


@cli.command()
@click.option('--job-id', required=True, help='Job ID to cancel')
def cancel(job_id):
    """
    Cancel a running job
    
    Example:
        python -m app.cli cancel --job-id <uuid>
    """
    async def _cancel():
        async with async_session_maker() as db:
            result = await db.execute(
                select(Job).where(Job.id == uuid.UUID(job_id))
            )
            job = result.scalar_one_or_none()
            
            if not job:
                click.echo(f"Job {job_id} not found", err=True)
                return
            
            if job.status not in ["pending", "running"]:
                click.echo(f"Cannot cancel job with status: {job.status}", err=True)
                return
            
            # Revoke Celery task
            from app.workers.celery_app import celery_app
            celery_app.control.revoke(str(job.id), terminate=True)
            
            # Update job status
            job.status = "cancelled"
            job.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
            await db.commit()
            
            click.echo(f"✅ Job {job_id} cancelled successfully")
    
    asyncio.run(_run_and_close(_cancel()))


@cli.command()
def stats():
    """
    Show overall statistics
    
    Example:
        python -m app.cli stats
    """
    async def _stats():
        async with async_session_maker() as db:
            from sqlalchemy import func
            
            # Total accounts
            total_accounts = await db.scalar(
                select(func.count()).select_from(Account)
            )
            
            # Discord accounts
            discord_count = await db.scalar(
                select(func.count()).select_from(Account).where(Account.platform == "discord")
            )
            
            # Gmail accounts
            gmail_count = await db.scalar(
                select(func.count()).select_from(Account).where(Account.platform == "gmail")
            )
            
            # Success rate
            discord_success = await db.scalar(
                select(func.count()).select_from(Account).where(
                    Account.platform == "discord",
                    Account.status == "success"
                )
            )
            
            gmail_success = await db.scalar(
                select(func.count()).select_from(Account).where(
                    Account.platform == "gmail",
                    Account.status == "success"
                )
            )
            
            # Total jobs
            total_jobs = await db.scalar(
                select(func.count()).select_from(Job)
            )
            
            click.echo("\n" + "="*60)
            click.echo("AAC Statistics")
            click.echo("="*60)
            click.echo(f"Total Accounts: {total_accounts}")
            click.echo(f"  Discord: {discord_count}")
            click.echo(f"  Gmail: {gmail_count}")
            click.echo(f"\nSuccess Rate:")
            click.echo(f"  Discord: {(discord_success/discord_count*100 if discord_count else 0):.1f}%")
            click.echo(f"  Gmail: {(gmail_success/gmail_count*100 if gmail_count else 0):.1f}%")
            click.echo(f"\nTotal Jobs: {total_jobs}")
            click.echo("="*60 + "\n")
    
    asyncio.run(_run_and_close(_stats()))


@cli.command()
def init_db():
    """
    Initialize database (create tables)
    
    Example:
        python -m app.cli init-db
    """
    async def _init():
        from app.core.database import engine
        from app.models.base import Base
        import app.models  # noqa: F401 - ensure all model modules are imported/registered

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        click.echo("✅ Database initialized successfully")

    asyncio.run(_run_and_close(_init()))


if __name__ == '__main__':
    cli()
