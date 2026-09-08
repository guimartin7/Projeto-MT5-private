$ErrorActionPreference = 'Stop'

# Gera o painel local somente leitura; nenhuma função de execução é incluída.
& .\.venv\Scripts\python.exe -m PyInstaller `
  --noconfirm --clean --windowed `
  --name ProjetoMT5Dashboard --distpath dist\latest desktop_dashboard.py

Write-Host "Executável gerado em dist\ProjetoMT5Dashboard\ProjetoMT5Dashboard.exe"
