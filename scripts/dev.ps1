# scripts/dev.ps1 - PowerShell helper for local development targets matching Makefile
[CmdletBinding()]
param(
    [Parameter(Position = 0, Mandatory = $true)]
    [ValidateSet("env", "up", "down", "logs", "ps", "lint", "fmt", "typecheck", "test", "opa-test", "pre-commit")]
    [string]$Target
)

$ErrorActionPreference = "Stop"
$ComposeCmd = "docker compose -f infra/docker-compose.yml --env-file infra/.env"

function Ensure-Env {
    if (-not (Test-Path "infra/.env")) {
        Write-Host "Creating infra/.env from infra/.env.example"
        Copy-Item "infra/.env.example" "infra/.env"
    }
}

switch ($Target) {
    "env" {
        Ensure-Env
    }
    "up" {
        Ensure-Env
        Invoke-Expression "$ComposeCmd up -d"
    }
    "down" {
        Invoke-Expression "$ComposeCmd down"
    }
    "logs" {
        Invoke-Expression "$ComposeCmd logs -f --tail=100"
    }
    "ps" {
        Invoke-Expression "$ComposeCmd ps"
    }
    "lint" {
        $dirs = Get-ChildItem -Path "libs", "services" -Directory | Where-Object { Test-Path "$($_.FullName)/pyproject.toml" }
        if ($dirs.Count -eq 0) {
            Write-Host "No pyproject.toml projects found yet."
            exit 0
        }
        foreach ($d in $dirs) {
            Write-Host "== lint $($d.FullName)"
            Push-Location $d.FullName
            try {
                ruff check .
                ruff format --check .
            } finally {
                Pop-Location
            }
        }
    }
    "fmt" {
        $dirs = Get-ChildItem -Path "libs", "services" -Directory | Where-Object { Test-Path "$($_.FullName)/pyproject.toml" }
        foreach ($d in $dirs) {
            Write-Host "== format $($d.FullName)"
            Push-Location $d.FullName
            try {
                ruff check --fix .
                ruff format .
            } finally {
                Pop-Location
            }
        }
    }
    "typecheck" {
        $dirs = Get-ChildItem -Path "libs", "services" -Directory | Where-Object { Test-Path "$($_.FullName)/pyproject.toml" }
        foreach ($d in $dirs) {
            Write-Host "== mypy $($d.FullName)"
            Push-Location $d.FullName
            try {
                mypy src
            } finally {
                Pop-Location
            }
        }
    }
    "test" {
        $dirs = Get-ChildItem -Path "libs", "services" -Directory | Where-Object { Test-Path "$($_.FullName)/pyproject.toml" }
        foreach ($d in $dirs) {
            Write-Host "== test $($d.FullName)"
            Push-Location $d.FullName
            try {
                pytest -q
            } finally {
                Pop-Location
            }
        }
    }
    "opa-test" {
        docker run --rm -v "${PWD}/policies:/policies" openpolicyagent/opa test /policies -v
    }
    "pre-commit" {
        pre-commit run --all-files
    }
}
