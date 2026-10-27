param([string]$Executavel, [string]$Saida)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

function Get-SafeLooseFiles([string]$Root, [string]$Boundary, [int]$Depth = 0) {
    if ($Depth -gt 6) { throw 'Pasta avulsa profunda demais.' }
    if (-not (Test-Path -LiteralPath $Root -PathType Container)) { return }
    $item = Get-Item -LiteralPath $Root
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { return }
    $ancestor = $item.FullName
    while ($ancestor.Length -ge $Boundary.Length) {
        if (((Get-Item -LiteralPath $ancestor).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Categoria avulsa com link/juncao.' }
        if ($ancestor -eq $Boundary) { break }; $ancestor = Split-Path -Parent $ancestor
    }
    foreach ($file in @(Get-ChildItem -LiteralPath $Root -File)) {
        if (($file.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0) { $file }
    }
    foreach ($directory in @(Get-ChildItem -LiteralPath $Root -Directory)) { Get-SafeLooseFiles $directory.FullName $Boundary ($Depth + 1) }
}

try {
    Add-Type -Path (Join-Path $PSScriptRoot 'Pes2017ResourceCollector.cs')
    if ([string]::IsNullOrWhiteSpace($Executavel)) {
        Add-Type -AssemblyName System.Windows.Forms
        $dialog = New-Object System.Windows.Forms.OpenFileDialog
        $dialog.Title = 'Selecione PES2017.exe na instalacao em que voce joga'
        $dialog.Filter = 'PES 2017 (PES2017.exe)|PES2017.exe'
        if ($dialog.ShowDialog() -ne 'OK') { exit 2 }
        $Executavel = $dialog.FileName; $dialog.Dispose()
    }
    $exe = Get-Item -LiteralPath $Executavel
    if ($exe.PSIsContainer -or $exe.Name -ine 'PES2017.exe') { throw 'Selecione o arquivo PES2017.exe.' }
    $installation = $exe.Directory.FullName
    if ([string]::IsNullOrWhiteSpace($Saida)) {
        $Saida = Join-Path $PSScriptRoot ('PES2017-recursos-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [Guid]::NewGuid().ToString('N').Substring(0,8))
    }
    if ((Test-Path -LiteralPath $Saida) -or (Test-Path -LiteralPath ($Saida + '.zip'))) { throw 'Escolha uma pasta de saida nova.' }
    $archives = @()
    foreach ($name in @('Data', 'download')) {
        $directory = Join-Path $installation $name
        if (Test-Path -LiteralPath $directory -PathType Container) {
            foreach ($file in @(Get-ChildItem -LiteralPath $directory -File -Filter '*.cpk' | Sort-Object Name)) {
                if (($file.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0) { $archives += @{ File=$file; Label=($name + '/' + $file.Name) } }
            }
        }
    }
    if ($archives.Count -eq 0) { throw 'Nao ha CPKs em Data/download. Escolha o executavel da instalacao completa.' }
    [void][IO.Directory]::CreateDirectory($Saida)
    $resources = Join-Path $Saida 'resources'
    $scans = @(); $errors = @(); $configs = @(); $loose = @(); $roots = @()
    [long]$remaining = 128MB
    foreach ($archive in $archives) {
        Write-Host ('Lendo indice: ' + $archive.Label)
        try {
            $scan = [FPSoccer.Pes2017.Collector]::Collect($archive.File.FullName,$archive.Label,$resources,$remaining)
            $scans += $scan; $remaining -= $scan.ExportedBytes
            if ($scan.Resources.Count -gt 0) { Write-Host ('  ' + $scan.Resources.Count + ' recursos selecionados.') -ForegroundColor Green }
        } catch {
            $reason = $_.Exception.Message.Replace($installation,'<instalacao>')
            $errors += @{ source=$archive.Label; error=$reason }
            Write-Host ('  Nao coletado: ' + $reason) -ForegroundColor Yellow
        }
    }
    foreach ($relative in @('sider.ini','gameplay.ini','download/DpFileList.bin')) {
        $path = Join-Path $installation $relative
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { continue }
        $file = Get-Item -LiteralPath $path
        if ($file.Length -gt 1MB -or (($file.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)) {
            $errors += @{source=$relative;error='Configuracao grande demais ou link.'}; continue
        }
        $destination = Join-Path (Join-Path $Saida 'configuration') ($relative.Replace('/','_'))
        [void][IO.Directory]::CreateDirectory((Split-Path -Parent $destination))
        $bytes = [IO.File]::ReadAllBytes($path)
        $stream = [IO.File]::Open($destination,[IO.FileMode]::CreateNew)
        try { $stream.Write($bytes,0,$bytes.Length) } finally { $stream.Dispose() }
        $configs += @{ source=$relative; stored=('configuration/' + [IO.Path]::GetFileName($destination)); sha256=[FPSoccer.Pes2017.Collector]::Hash($bytes); bytes=$bytes.Length }
        if ($relative -eq 'sider.ini') {
            # Read configured roots only, without executing any Lua/module.
            foreach ($line in [IO.File]::ReadAllLines($path)) {
                if ($line -match '^\s*cpk\.root\s*=\s*"([^"]+)"') { $roots += $Matches[1] }
            }
        }
    }
    $rootIndex = 0
    foreach ($configured in $roots) {
        $rootIndex++
        try {
            $full = [IO.Path]::GetFullPath((Join-Path $installation $configured))
            $prefix = $installation.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
            if (-not $full.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase)) { throw 'Raiz avulsa fora da instalacao; nao lida.' }
            # Check each ancestor so an interior root cannot follow a junction.
            $ancestor = $full
            while ($ancestor.Length -ge $installation.Length) {
                if ((Test-Path -LiteralPath $ancestor) -and (((Get-Item -LiteralPath $ancestor).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)) { throw 'Raiz avulsa com link/juncao; nao lida.' }
                if ($ancestor -eq $installation) { break }; $ancestor = Split-Path -Parent $ancestor
            }
            foreach ($category in @('common/match/constant','common/anime/playerID/bin','common/anime/AnimeTable/bin','common/anime/Mbinfo/bin')) {
                foreach ($file in @(Get-SafeLooseFiles (Join-Path $full $category) $installation)) {
                    $virtual = $file.FullName.Substring($full.TrimEnd([IO.Path]::DirectorySeparatorChar).Length + 1).Replace('\','/')
                    if (-not [FPSoccer.Pes2017.Collector]::IsTarget($virtual)) { continue }
                    $resource = [FPSoccer.Pes2017.Collector]::CollectLoose($file.FullName,('configured-root-' + $rootIndex),$virtual,$resources,$remaining)
                    $loose += $resource; $remaining -= $resource.StoredBytes
                }
            }
        } catch { $errors += @{source=('configured-root-' + $rootIndex);error=$_.Exception.Message.Replace($installation,'<instalacao>')} }
    }
    $manifest = @{ schema_version=1; kind='pes2017-selective-stored-resources'; created_utc=[DateTime]::UtcNow.ToString('o');
        executable_sha256=[FPSoccer.Pes2017.Collector]::HashFile($exe.FullName);
        archives=@($scans); loose_resources=@($loose); configurations=@($configs); errors=@($errors);
        configured_loose_root_count=$roots.Count; export_limit_bytes=128MB; exported_bytes=(128MB - $remaining);
        load_order_verified=$false; runtime_enabled=$false;
        scope='Bytes armazenados preservados; constantes e metadados de animacao selecionados. Nenhum executavel, DLL, textura ou captura de animacao copiado. Nenhum jogo/modulo executado ou alterado.';
        limits=@('Recursos comprimidos preservados; descompressao e verificacao posteriores.', 'Ordem de carregamento e uso em execucao ainda nao confirmados.', 'CPKs acima de 512 MiB nao recebem hash integral; recursos selecionados sempre recebem.', 'Somente configuracoes sider.ini, gameplay.ini e DpFileList.bin acompanham a coleta.') }
    $manifest | ConvertTo-Json -Depth 14 | Set-Content -LiteralPath (Join-Path $Saida 'manifesto.json') -Encoding UTF8
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = $Saida + '.zip'
    [IO.Compression.ZipFile]::CreateFromDirectory($Saida,$zip)
    Write-Host ''
    if ((Get-Item -LiteralPath $zip).Length -le 30MB) {
        Write-Host ('Pronto. Envie este ZIP: ' + $zip) -ForegroundColor Green
    } else {
        $parts = @(); $inputStream = [IO.File]::OpenRead($zip); $buffer = New-Object byte[] (1MB); $index=1
        try {
            while ($inputStream.Position -lt $inputStream.Length) {
                $part = $zip + ('.part{0:D3}' -f $index); $stream = [IO.File]::Open($part,[IO.FileMode]::CreateNew)
                try {
                    $left=24MB
                    while ($left -gt 0) { $count=$inputStream.Read($buffer,0,[Math]::Min($left,$buffer.Length));if($count -eq 0){break};$stream.Write($buffer,0,$count);$left-=$count }
                } finally { $stream.Dispose() }
                $parts += @{file=[IO.Path]::GetFileName($part);bytes=(Get-Item -LiteralPath $part).Length;sha256=[FPSoccer.Pes2017.Collector]::HashFile($part)}; $index++
            }
        } finally { $inputStream.Dispose() }
        @{original=[IO.Path]::GetFileName($zip);sha256=[FPSoccer.Pes2017.Collector]::HashFile($zip);parts=@($parts)} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath ($zip + '.partes.json') -Encoding UTF8
        Write-Host ('Pronto. ZIP grande dividido: envie TODAS as partes .part001/.part002 e o .partes.json em ' + $PSScriptRoot) -ForegroundColor Green
    }
    if ($errors.Count -gt 0) { Write-Host 'O manifesto inclui os arquivos que nao puderam ser lidos. Envie o resultado mesmo assim.' }
} catch { Write-Host ('ERRO: ' + $_.Exception.Message) -ForegroundColor Red; exit 1 }
