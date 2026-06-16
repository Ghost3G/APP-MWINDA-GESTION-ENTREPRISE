$PythonExe = "C:\Program Files\PostgreSQL\18\pgAdmin 4\python\python.exe"

if (-not (Test-Path -LiteralPath $PythonExe)) {
    Write-Error "Python introuvable: $PythonExe"
    exit 1
}

& $PythonExe "$PSScriptRoot\manage_local.py" @args
