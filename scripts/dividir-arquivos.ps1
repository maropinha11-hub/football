param([string[]]$Paths)
$ErrorActionPreference = 'Stop'
try {
    if (-not $Paths) {
        Add-Type -AssemblyName System.Windows.Forms
        $dialog = New-Object System.Windows.Forms.OpenFileDialog
        $dialog.Title = 'Escolha os ZIPs de animacoes e dados para dividir'
        $dialog.Filter = 'Arquivos ZIP (*.zip)|*.zip|Todos os arquivos (*.*)|*.*'
        $dialog.Multiselect = $true
        if ($dialog.ShowDialog() -ne 'OK') { exit 0 }
        $Paths = $dialog.FileNames
    }
    foreach ($item in $Paths) {
        $source = Get-Item -LiteralPath $item
        if ($source.PSIsContainer) { throw 'Selecione arquivos, nao pastas.' }
        $destination = $source.FullName + '.partes-' + [Guid]::NewGuid().ToString('N').Substring(0,8)
        [void][IO.Directory]::CreateDirectory($destination)
        $inputStream = [IO.File]::OpenRead($source.FullName)
        $parts = @()
        try {
            $buffer = New-Object byte[] (1MB)
            $index = 1
            while ($inputStream.Position -lt $inputStream.Length) {
                $name = $source.Name + ('.part{0:D3}' -f $index)
                $path = Join-Path $destination $name
                $outputStream = [IO.File]::Open($path, [IO.FileMode]::CreateNew)
                try {
                    $remaining = 30MB
                    while ($remaining -gt 0) {
                        $count = $inputStream.Read($buffer,0,[Math]::Min($buffer.Length,$remaining))
                        if ($count -eq 0) { break }
                        $outputStream.Write($buffer,0,$count)
                        $remaining -= $count
                    }
                } finally { $outputStream.Dispose() }
                $parts += @{ name=$name; bytes=(Get-Item -LiteralPath $path).Length; sha256=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLower() }
                $index++
            }
        } finally { $inputStream.Dispose() }
        @{ original=$source.Name; bytes=$source.Length; sha256=(Get-FileHash -LiteralPath $source.FullName -Algorithm SHA256).Hash.ToLower(); parts=$parts } |
            ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $destination 'manifest.json') -Encoding UTF8
        Write-Host "Pronto: $destination" -ForegroundColor Green
        Write-Host 'Envie o manifest.json e TODAS as partes .part001, .part002, etc. O ZIP original foi preservado.'
    }
} catch { Write-Host $_ -ForegroundColor Red; exit 1 }
