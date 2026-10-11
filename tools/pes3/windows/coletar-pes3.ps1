param([string]$PastaIso, [string]$Saida)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0
try {
    Add-Type -Path (Join-Path $PSScriptRoot 'Pes3ResourceCollector.cs')
    if ([string]::IsNullOrWhiteSpace($PastaIso)) {
        Add-Type -AssemblyName System.Windows.Forms
        $dialogo = New-Object System.Windows.Forms.FolderBrowserDialog
        $dialogo.Description = 'Selecione a pasta da ISO EXTRAIDA contendo DATA_F.AFS / DATA_G.AFS / DATA_S.AFS.'
        if ($dialogo.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) { exit 2 }
        $PastaIso = $dialogo.SelectedPath
        $dialogo.Dispose()
    }
    $PastaIso = (Resolve-Path -LiteralPath $PastaIso).ProviderPath
    if ([string]::IsNullOrWhiteSpace($Saida)) {
        $Saida = Join-Path $PSScriptRoot ('PES3-recursos-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [Guid]::NewGuid().ToString('N').Substring(0,8))
    }
    if (Test-Path -LiteralPath $Saida) { throw 'A pasta de saida ja existe. Escolha uma nova pasta para preservar a coleta anterior.' }
    $arquivos = @(Get-ChildItem -LiteralPath $PastaIso -File | Where-Object { $_.Name -match '^DATA_[EFGIS]\.AFS$' } | Sort-Object Name)
    if ($arquivos.Count -eq 0) { throw 'Nenhum DATA_E/F/G/I/S.AFS encontrado. Selecione a pasta da ISO extraida.' }
    $executavel = Join-Path $PastaIso 'SLES_519.12'
    $hashExecutavel = $null
    if (Test-Path -LiteralPath $executavel -PathType Leaf) {
        $hashExecutavel = [FPSoccer.Pes3.ResourceCollector]::HashFile($executavel)
        if ($hashExecutavel -ne [FPSoccer.Pes3.ResourceCollector]::ExecutableSha256) { throw 'SLES_519.12 difere da revisao estudada. Nenhum recurso foi coletado.' }
    }
    [IO.Directory]::CreateDirectory($Saida) | Out-Null
    $registros = @(); $falhas = @()
    foreach ($arquivo in $arquivos) {
        Write-Host ('Lendo ' + $arquivo.Name + '...')
        try { $registros += [FPSoccer.Pes3.ResourceCollector]::Collect($arquivo.FullName, (Join-Path $Saida 'recursos')) }
        catch { $falhas += @{ arquivo = $arquivo.Name; motivo = $_.Exception.Message }; Write-Host ('Nao correspondeu: ' + $_.Exception.Message) }
    }
    $manifesto = @{ schema_version = 1; criado_utc = [DateTime]::UtcNow.ToString('o'); sles_sha256 = $hashExecutavel;
        descritores_sles_sha256 = [FPSoccer.Pes3.ResourceCollector]::ExecutableSha256;
        modo = 'leitura; bytes armazenados preservados; zlib sera validado na importacao quando presente; game.mbc bruto preservado';
        recursos = @($registros); arquivos_nao_correspondentes = @($falhas) }
    $manifesto | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $Saida 'manifesto.json') -Encoding UTF8
    if ($registros.Count -eq 0) { throw ('Nenhum DATA correspondeu. Envie manifesto.json da pasta ' + $Saida) }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = $Saida + '.zip'
    [IO.Compression.ZipFile]::CreateFromDirectory($Saida, $zip, [IO.Compression.CompressionLevel]::Optimal, $false)
    Write-Host ''
    Write-Host ('Pronto. Envie este ZIP na conversa: ' + $zip) -ForegroundColor Green
    Write-Host ('SHA256: ' + [FPSoccer.Pes3.ResourceCollector]::HashFile($zip))
    exit 0
} catch {
    Write-Host ('ERRO: ' + $_.Exception.Message) -ForegroundColor Red
    exit 1
}
