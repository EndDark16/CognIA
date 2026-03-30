$hostName = "smtp.gmail.com"
$port = 587

$tcp = New-Object System.Net.Sockets.TcpClient
$tcp.ReceiveTimeout = 15000
$tcp.SendTimeout = 15000

try {
    $tcp.Connect($hostName, $port)
    $stream = $tcp.GetStream()
    $reader = New-Object System.IO.StreamReader($stream)
    $writer = New-Object System.IO.StreamWriter($stream)
    $writer.NewLine = "`r`n"
    $writer.AutoFlush = $true

    $banner = $reader.ReadLine()
    Write-Host "BANNER:" $banner

    $writer.WriteLine("EHLO localhost")
    while ($true) {
        $line = $reader.ReadLine()
        Write-Host $line
        if ($line -match "^250 ") { break }
    }

    $writer.WriteLine("STARTTLS")
    $resp = $reader.ReadLine()
    Write-Host "STARTTLS:" $resp
    if ($resp -notmatch "^220") {
        throw "STARTTLS not accepted"
    }

    $ssl = New-Object System.Net.Security.SslStream($stream, $false)
    $ssl.AuthenticateAsClient($hostName)
    Write-Host "TLS handshake OK"
} catch {
    Write-Host "ERROR:" $_.Exception.Message
} finally {
    if ($tcp.Connected) { $tcp.Close() }
}
