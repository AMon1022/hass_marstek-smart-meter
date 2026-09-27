param(
    [Parameter(Mandatory=$false)]
    [string]$Ip,
    [Parameter(Mandatory=$false)]
    [string]$CtMac,
    [string]$BatteryMac = "001122334455",
    [string]$DeviceType = "HMG-50",
    [string]$CtType = "HME-4"
)

if (-not $Ip -or -not $CtMac) {
    Write-Host "Usage: .\test_ct.ps1 -Ip <IP_CT> -CtMac <MAC_CT_APP> [-BatteryMac <MAC_BATTERY>] [-DeviceType HMG-50] [-CtType HME-4]" -ForegroundColor Yellow
    Write-Host "Exemple: .\test_ct.ps1 -Ip 192.168.1.50 -CtMac 123456abcdef" -ForegroundColor Cyan
    exit 1
}

$CtMac = ($CtMac -replace "[:-]", "").Trim()
$BatteryMac = ($BatteryMac -replace "[:-]", "").Trim()

function Build-Payload($devType, $batMac, $cType, $cMac) {
    $soh = [byte]0x01
    $stx = [byte]0x02
    $etx = [byte]0x03
    $sep = '|'
    $fields = @($devType, $batMac, $cType, $cMac, '0', '0')
    $msgStr = $sep + ($fields -join $sep)
    $msgBytes = [System.Text.Encoding]::ASCII.GetBytes($msgStr)
    $baseSize = 1 + 1 + $msgBytes.Length + 1 + 2
    $totalLen = 0
    for ($digits = 1; $digits -le 4; $digits++) {
        $candidate = $baseSize + $digits
        if ($candidate.ToString().Length -eq $digits) {
            $totalLen = $candidate
            break
        }
    }
    $lenBytes = [System.Text.Encoding]::ASCII.GetBytes($totalLen.ToString())
    $payload = [System.Collections.Generic.List[byte]]::new()
    $payload.Add($soh)
    $payload.Add($stx)
    $payload.AddRange($lenBytes)
    $payload.AddRange($msgBytes)
    $payload.Add($etx)
    $xor = 0
    foreach ($b in $payload) { $xor = $xor -bxor $b }
    $checksumBytes = [System.Text.Encoding]::ASCII.GetBytes(("{0:x2}" -f $xor))
    $payload.AddRange($checksumBytes)
    return $payload.ToArray()
}

Write-Host "=== Test interrogation UDP CT-002 ($Ip:12345) ===" -ForegroundColor Cyan
Write-Host "CT MAC      : $CtMac"
Write-Host "Battery MAC : $BatteryMac"
Write-Host "Device Type : $DeviceType"
Write-Host "CT Type     : $CtType"
Write-Host ""

$tests = @(
    @{ Name = "CT MAC en minuscules, DeviceType $DeviceType"; CtMac = $CtMac.ToLower(); DevType = $DeviceType; BatMac = $BatteryMac.ToUpper() },
    @{ Name = "CT MAC en majuscules, DeviceType $DeviceType"; CtMac = $CtMac.ToUpper(); DevType = $DeviceType; BatMac = $BatteryMac.ToUpper() },
    @{ Name = "CT MAC en minuscules, Battery MAC 001122334455"; CtMac = $CtMac.ToLower(); DevType = "HMG-50"; BatMac = "001122334455" }
)

$remoteEP = New-Object System.Net.IPEndPoint([System.Net.IPAddress]::Any, 0)

foreach ($test in $tests) {
    Write-Host "Test: $($test.Name)..." -NoNewline
    $payload = Build-Payload -devType $test.DevType -batMac $test.BatMac -cType $CtType -cMac $test.CtMac
    $client = New-Object System.Net.Sockets.UdpClient
    $client.Client.ReceiveTimeout = 2500
    try {
        $dest = New-Object System.Net.IPEndPoint([System.Net.IPAddress]::Parse($Ip), 12345)
        [void]$client.Send($payload, $payload.Length, $dest)
        $receivedBytes = $client.Receive([ref]$remoteEP)
        Write-Host " [REPONSE RECUE !]" -ForegroundColor Green
        
        $rawStr = [System.Text.Encoding]::ASCII.GetString($receivedBytes)
        Write-Host "Données brutes reçues : $rawStr" -ForegroundColor Yellow
        
        # Décodage
        $sepIdx = -1
        for ($i = 2; $i -lt $receivedBytes.Length; $i++) {
            if ($receivedBytes[$i] -eq 0x7C) { # '|'
                $sepIdx = $i
                break
            }
        }
        if ($sepIdx -ne -1) {
            $msgPart = [System.Text.Encoding]::ASCII.GetString($receivedBytes, $sepIdx, $receivedBytes.Length - $sepIdx - 3)
            $fields = $msgPart.Split('|')
            Write-Host "`nChamps détectés :" -ForegroundColor Green
            $labels = @(
                "meter_dev_type", "meter_mac_code", "hhm_dev_type", "hhm_mac_code",
                "A_phase_power (W)", "B_phase_power (W)", "C_phase_power (W)", "total_power (W)",
                "A_chrg_nb", "B_chrg_nb", "C_chrg_nb", "ABC_chrg_nb", "wifi_rssi (dBm)"
            )
            for ($k = 0; $k -lt [Math]::Min($labels.Length, $fields.Length - 1); $k++) {
                Write-Host "  $($labels[$k]): $($fields[$k+1])"
            }
        }
        $client.Close()
        exit 0
    } catch [System.Net.Sockets.SocketException] {
        Write-Host " [Timeout - Pas de reponse]" -ForegroundColor Red
    } catch {
        Write-Host " [Erreur: $($_.Exception.Message)]" -ForegroundColor Red
    } finally {
        $client.Close()
    }
}

Write-Host "`nAucun test n'a recu de reponse. Verifiez l'adresse IP, le port UDP 12345, et que le CT MAC est bien celui de l'application." -ForegroundColor Yellow
