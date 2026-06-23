# ─── VoiceMarket Docker Manager ────────────────────────────────────────────────
# Usage: .\docker-manage.ps1 [command]
# Commands: up, down, restart, logs, shell, migrate, createsuperuser, status, clean

param(
    [Parameter(Position=0)]
    [string]$Command = "help"
)

$PROJECT = "voicemarket"
$COMPOSE_FILE = "docker-compose.yml"

function Write-Header {
    param([string]$msg)
    Write-Host ""
    Write-Host "  ============================================" -ForegroundColor Cyan
    Write-Host "   $msg" -ForegroundColor Cyan
    Write-Host "  ============================================" -ForegroundColor Cyan
    Write-Host ""
}

switch ($Command.ToLower()) {

    "up" {
        Write-Header "Starting VoiceMarket..."
        docker compose -f $COMPOSE_FILE up -d --build
        Write-Host ""
        Write-Host "  ✅ All services started!" -ForegroundColor Green
        Write-Host "  🌐 Website:  http://localhost:8000" -ForegroundColor Yellow
        Write-Host "  🛡️  Admin:    http://localhost:8000/admin/" -ForegroundColor Yellow
        Write-Host "  📖 API Docs: http://localhost:8000/api/docs/" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "  Run .\docker-manage.ps1 logs to view logs." -ForegroundColor Gray
    }

    "down" {
        Write-Header "Stopping VoiceMarket..."
        docker compose -f $COMPOSE_FILE down
        Write-Host "  ✅ All containers stopped." -ForegroundColor Green
    }

    "restart" {
        Write-Header "Restarting VoiceMarket..."
        docker compose -f $COMPOSE_FILE restart
        Write-Host "  ✅ Restarted." -ForegroundColor Green
    }

    "build" {
        Write-Header "Rebuilding Docker images..."
        docker compose -f $COMPOSE_FILE build --no-cache
        Write-Host "  ✅ Build complete." -ForegroundColor Green
    }

    "logs" {
        Write-Host "  📄 Streaming logs (Ctrl+C to stop)..." -ForegroundColor Cyan
        docker compose -f $COMPOSE_FILE logs -f --tail=100
    }

    "logs-web" {
        docker compose -f $COMPOSE_FILE logs -f --tail=100 web
    }

    "logs-celery" {
        docker compose -f $COMPOSE_FILE logs -f --tail=100 celery
    }

    "shell" {
        Write-Host "  🐚 Opening Django shell in web container..." -ForegroundColor Cyan
        docker compose -f $COMPOSE_FILE exec web python manage.py shell
    }

    "bash" {
        Write-Host "  🐚 Opening bash in web container..." -ForegroundColor Cyan
        docker compose -f $COMPOSE_FILE exec web bash
    }

    "migrate" {
        Write-Header "Running migrations..."
        docker compose -f $COMPOSE_FILE exec web python manage.py migrate --noinput
        Write-Host "  ✅ Migrations applied." -ForegroundColor Green
    }

    "makemigrations" {
        Write-Header "Making migrations..."
        docker compose -f $COMPOSE_FILE exec web python manage.py makemigrations
    }

    "createsuperuser" {
        Write-Header "Creating superuser..."
        docker compose -f $COMPOSE_FILE exec web python manage.py createsuperuser
    }

    "collectstatic" {
        Write-Header "Collecting static files..."
        docker compose -f $COMPOSE_FILE exec web python manage.py collectstatic --noinput --clear
        Write-Host "  ✅ Static files collected." -ForegroundColor Green
    }

    "status" {
        Write-Header "Container Status"
        docker compose -f $COMPOSE_FILE ps
    }

    "clean" {
        Write-Header "Cleaning up containers and volumes..."
        $confirm = Read-Host "  ⚠️  This will delete ALL data (database, media). Type 'yes' to confirm"
        if ($confirm -eq "yes") {
            docker compose -f $COMPOSE_FILE down -v --remove-orphans
            Write-Host "  ✅ All containers and volumes removed." -ForegroundColor Green
        } else {
            Write-Host "  ❌ Cancelled." -ForegroundColor Red
        }
    }

    "ps" {
        docker compose -f $COMPOSE_FILE ps
    }

    default {
        Write-Host ""
        Write-Host "  🎙  VoiceMarket Docker Manager" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "  Usage: .\docker-manage.ps1 [command]" -ForegroundColor White
        Write-Host ""
        Write-Host "  Commands:" -ForegroundColor Yellow
        Write-Host "    up              Start all services (builds if needed)"
        Write-Host "    down            Stop all services"
        Write-Host "    restart         Restart all services"
        Write-Host "    build           Rebuild Docker images (no cache)"
        Write-Host "    logs            Stream all logs"
        Write-Host "    logs-web        Stream web server logs only"
        Write-Host "    logs-celery     Stream celery worker logs only"
        Write-Host "    shell           Open Django shell"
        Write-Host "    bash            Open bash in web container"
        Write-Host "    migrate         Run database migrations"
        Write-Host "    makemigrations  Make new migrations"
        Write-Host "    createsuperuser Create a Django admin superuser"
        Write-Host "    collectstatic   Collect static files"
        Write-Host "    status / ps     Show container status"
        Write-Host "    clean           Remove containers + volumes (DELETES DATA)"
        Write-Host ""
        Write-Host "  Quick start:" -ForegroundColor Green
        Write-Host "    .\docker-manage.ps1 up"
        Write-Host "    .\docker-manage.ps1 createsuperuser"
        Write-Host ""
    }
}
