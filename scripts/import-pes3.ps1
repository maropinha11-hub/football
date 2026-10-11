param([string]$Source, [string]$Destination)
$ErrorActionPreference = 'Stop'
try {
    if (-not $Source) {
        Add-Type -AssemblyName System.Windows.Forms
        $picker = New-Object System.Windows.Forms.OpenFileDialog
        $picker.Title = 'Selecione fpsoccer-pes-nucleo-v14.zip ou pes_animation_tracks.fpsa'
        $picker.Filter = 'Banco PES3 (*.zip;*.fpsa)|*.zip;*.fpsa'
        if ($picker.ShowDialog() -ne 'OK') { Write-Host 'Importacao cancelada.'; exit 0 }
        $Source = $picker.FileName
        $picker.Dispose()
    }
    if (-not $Destination) { $Destination = Join-Path $PSScriptRoot 'pes3/pes_animation_tracks.fpsa' }
    $Source = [IO.Path]::GetFullPath($Source)
    $Destination = [IO.Path]::GetFullPath($Destination)
    $expectedHash = 'c40813d6b23f77834877ba4a5863ae54f8b829f6fc8f2c606d373c618d26bbe5'
    if ([IO.Path]::GetExtension($Source) -ieq '.zip') {
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $archive = [IO.Compression.ZipFile]::OpenRead($Source)
        try {
            # Read one pinned numeric entry, without extracting executable files
            # or interpreting paths from the supplied archive.
            $entries = @($archive.Entries | Where-Object { ($_.FullName -replace '\\','/').Split('/')[-1] -ceq 'pes_animation_tracks.fpsa' })
            if ($entries.Count -ne 1 -or $entries[0].Length -ne 6310088) {
                throw 'O ZIP deve conter exatamente o banco pes_animation_tracks.fpsa do nucleo v14.'
            }
            $stream = $entries[0].Open()
            $memory = New-Object IO.MemoryStream
            try {
                $chunk = New-Object byte[] 65536
                while (($read = $stream.Read($chunk,0,$chunk.Length)) -gt 0) {
                    if ($memory.Length + $read -gt 6310088) { throw 'Entrada FPSA excede o tamanho conferido.' }
                    $memory.Write($chunk,0,$read)
                }
                $bytes = $memory.ToArray()
            }
            finally { $stream.Dispose(); $memory.Dispose() }
        } finally { $archive.Dispose() }
    } elseif ([IO.Path]::GetExtension($Source) -ieq '.fpsa') {
        if ((Get-Item -LiteralPath $Source).Length -ne 6310088) { throw 'Tamanho do banco FPSANM14 incorreto.' }
        $bytes = [IO.File]::ReadAllBytes($Source)
    } else { throw 'Selecione o ZIP do nucleo v14 ou seu arquivo .fpsa.' }
    $hasher = [Security.Cryptography.SHA256]::Create()
    try { $hash = [BitConverter]::ToString($hasher.ComputeHash($bytes)).Replace('-','').ToLowerInvariant() }
    finally { $hasher.Dispose() }
    if ($bytes.Length -ne 6310088 -or $hash -cne $expectedHash) { throw 'Banco diferente do arquivo PES3 analisado, ou corrompido. Nenhum arquivo instalado.' }
    $folder = [IO.Path]::GetDirectoryName($Destination)
    [IO.Directory]::CreateDirectory($folder) | Out-Null
    $temporary = Join-Path $folder ([Guid]::NewGuid().ToString()+'.tmp')
    $backup = Join-Path $folder ([Guid]::NewGuid().ToString()+'.backup')
    try {
        [IO.File]::WriteAllBytes($temporary,$bytes)
        if ([IO.File]::Exists($Destination)) {
            [IO.File]::Replace($temporary,$Destination,$backup)
        } else { [IO.File]::Move($temporary,$Destination) }
    } finally {
        if ([IO.File]::Exists($temporary)) { [IO.File]::Delete($temporary) }
        if ([IO.File]::Exists($backup)) { [IO.File]::Delete($backup) }
    }
    Write-Host 'Instaladas 1105 animacoes. Execute estudar-pes3.bat.'
    Write-Host 'F7 abre/fecha o estudo; F8/F9 trocam clip; F10 pausa; F11 avanca; C mostra clips dos saves.'
    Write-Host 'Esse modo exibe o esqueleto original ao lado do jogador. A gameplay nativa continua ativa.'
    exit 0
} catch {
    Write-Host ('ERRO: '+$_.Exception.Message)
    exit 1
}
