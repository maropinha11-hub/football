param([string]$Executavel, [string]$Saida)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

function Get-PeMetadata([string]$Path) {
    $stream = [IO.File]::Open($Path, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
    $reader = [System.IO.BinaryReader]::new($stream)
    try {
        if ($stream.Length -lt 64 -or $reader.ReadUInt16() -ne 0x5A4D) { throw 'Assinatura MZ ausente.' }
        $stream.Position = 0x3C
        $pe = [long]$reader.ReadUInt32()
        if ($pe + 24 -gt $stream.Length) { throw 'Cabecalho PE fora do arquivo.' }
        $stream.Position = $pe
        if ($reader.ReadUInt32() -ne 0x4550) { throw 'Assinatura PE ausente.' }
        $machine = $reader.ReadUInt16()
        $count = $reader.ReadUInt16()
        $timestamp = $reader.ReadUInt32()
        $stream.Position = $pe + 20
        $optionalSize = $reader.ReadUInt16()
        $characteristics = $reader.ReadUInt16()
        $optional = $pe + 24
        $table = $optional + $optionalSize
        if ($count -lt 1 -or $count -gt 96 -or $table + 40 * $count -gt $stream.Length) { throw 'Tabela de secoes invalida.' }
        $stream.Position = $optional
        $magic = $reader.ReadUInt16()
        if ($magic -eq 0x20B) { $bits = 64; $baseOffset = 24; $minimum = 112 }
        elseif ($magic -eq 0x10B) { $bits = 32; $baseOffset = 28; $minimum = 96 }
        else { throw 'Formato PE opcional desconhecido.' }
        if ($optionalSize -lt $minimum) { throw 'Cabecalho opcional incompleto.' }
        $stream.Position = $optional + 16
        $entry = $reader.ReadUInt32()
        $stream.Position = $optional + $baseOffset
        if ($bits -eq 64) { $imageBase = $reader.ReadUInt64() } else { $imageBase = $reader.ReadUInt32() }
        $sections = @()
        for ($i = 0; $i -lt $count; $i++) {
            $stream.Position = $table + $i * 40
            $name = [Text.Encoding]::ASCII.GetString($reader.ReadBytes(8)).TrimEnd([char]0)
            $virtualSize = $reader.ReadUInt32(); $rva = $reader.ReadUInt32()
            $rawSize = $reader.ReadUInt32(); $rawOffset = $reader.ReadUInt32()
            if ([long]$rawOffset + $rawSize -gt $stream.Length) { throw 'Secao fora do arquivo.' }
            $stream.Position = $table + $i * 40 + 36
            $flags = $reader.ReadUInt32()
            $sections += @{ name=$name; rva=$rva; virtual_size=$virtualSize; raw_offset=$rawOffset; raw_size=$rawSize; characteristics=$flags }
        }
        return @{ bits=$bits; machine=$machine; coff_timestamp_raw=$timestamp; image_base=$imageBase;
                  entry_rva=$entry; characteristics=$characteristics; sections=@($sections);
                  scope='Cabecalhos somente; nenhuma funcao ou parametro de gameplay identificado.' }
    } finally { $reader.Dispose(); $stream.Dispose() }
}

try {
    if ([string]::IsNullOrWhiteSpace($Executavel)) {
        Add-Type -AssemblyName System.Windows.Forms
        $dialog = New-Object System.Windows.Forms.OpenFileDialog
        $dialog.Title = 'Escolha PES2017.exe na instalacao do seu jogo'
        $dialog.Filter = 'Executavel PES 2017 (PES2017.exe)|PES2017.exe|Executaveis (*.exe)|*.exe'
        if ($dialog.ShowDialog() -ne 'OK') { exit 2 }
        $Executavel = $dialog.FileName
        $dialog.Dispose()
    }
    $exe = Get-Item -LiteralPath $Executavel
    if ($exe.PSIsContainer) { throw 'Selecione o executavel, nao uma pasta.' }
    $installation = $exe.Directory.FullName
    if ([string]::IsNullOrWhiteSpace($Saida)) {
        $Saida = Join-Path $PSScriptRoot ('PES2017-inventario-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [Guid]::NewGuid().ToString('N').Substring(0,8))
    }
    if (Test-Path -LiteralPath $Saida) { throw 'Escolha uma pasta de saida nova.' }
    $pe = Get-PeMetadata $exe.FullName
    Write-Host 'Calculando SHA256 do executavel...'
    $exeHash = (Get-FileHash -LiteralPath $exe.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    $files = @(); $errors = @()
    # Explicit game directories only. Do not scan other disks, profiles or saved games.
    foreach ($relative in @('', 'Data', 'download')) {
        $directory = if ($relative -eq '') { $installation } else { Join-Path $installation $relative }
        if (-not (Test-Path -LiteralPath $directory -PathType Container)) { continue }
        foreach ($file in @(Get-ChildItem -LiteralPath $directory -File | Sort-Object Name)) {
            if ($file.Extension -notmatch '^\.(exe|dll|cpk|bin|dat|ini)$') { continue }
            try {
                $stream = [IO.File]::OpenRead($file.FullName)
                try {
                    $header = New-Object byte[] (32)
                    $read = $stream.Read($header,0,32)
                    $hex = ([BitConverter]::ToString($header,0,$read)).Replace('-','').ToLowerInvariant()
                } finally { $stream.Dispose() }
                $name = if ($relative -eq '') { $file.Name } else { $relative + '/' + $file.Name }
                $fileHash = $null
                if ($file.FullName -eq $exe.FullName) { $fileHash = $exeHash }
                $files += @{ relative_path=$name; bytes=$file.Length; first_32_bytes_hex=$hex;
                             full_file_sha256=$fileHash }
            } catch { $errors += @{ file=$file.Name; error=$_.Exception.Message } }
        }
    }
    [void][IO.Directory]::CreateDirectory($Saida)
    $manifest = @{ schema_version=1; kind='local_read_only_installation_inventory'; created_utc=[DateTime]::UtcNow.ToString('o');
                   executable=@{ file=$exe.Name; bytes=$exe.Length; sha256=$exeHash; pe=$pe };
                   files=@($files); errors=@($errors);
                   scope='Inventario de nomes relativos, tamanhos e cabecalhos. Nao e extracao/decompilacao de gameplay. Nao executa, injeta ou altera o jogo.';
                   limitations=@('Dados CPK e DLL nao foram copiados ou decodificados.', 'So o executavel recebeu hash integral.', 'Movimentos e parametros do PES ainda nao foram medidos.') }
    $manifest | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $Saida 'inventario.json') -Encoding UTF8
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = $Saida + '.zip'
    [IO.Compression.ZipFile]::CreateFromDirectory($Saida,$zip)
    Write-Host ('Pronto. Envie o ZIP pequeno: ' + $zip) -ForegroundColor Green
} catch {
    Write-Host ('ERRO: ' + $_.Exception.Message) -ForegroundColor Red
    exit 1
}
