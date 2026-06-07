$ProjectRoot = "C:\Users\SrikanthMudaliar\AI-Cloud-Advisor"
$ThresholdMinutes = 45
$Now = Get-Date

$AwsLog = Join-Path $ProjectRoot "aws_sync.log"
$GcpLog = Join-Path $ProjectRoot "gcp_sync.log"
$AzureLog = Join-Path $ProjectRoot "azure_sync.log"
$AlertLog = Join-Path $ProjectRoot "sync_health_alerts.log"
$StatusLog = Join-Path $ProjectRoot "sync_health_status.log"

function Test-SyncLog {
    param(
        [string]$LogPath,
        [string]$Name,
        [string]$SuccessPattern,
        [datetime]$CurrentTime,
        [int]$MaxAgeMinutes
    )

    if (-not (Test-Path $LogPath)) {
        return [pscustomobject]@{
            Name = $Name
            Healthy = $false
            Reason = "missing log file"
            AgeMinutes = $null
        }
    }

    $item = Get-Item $LogPath
    $age = ($CurrentTime - $item.LastWriteTime).TotalMinutes
    $tail = Get-Content $LogPath -Tail 50
    $hasSuccess = $tail -match $SuccessPattern

    if ($age -gt $MaxAgeMinutes) {
        return [pscustomobject]@{
            Name = $Name
            Healthy = $false
            Reason = "stale log (${([math]::Round($age,2))} minutes old)"
            AgeMinutes = [math]::Round($age,2)
        }
    }

    if (-not $hasSuccess) {
        return [pscustomobject]@{
            Name = $Name
            Healthy = $false
            Reason = "no success marker in recent log lines"
            AgeMinutes = [math]::Round($age,2)
        }
    }

    return [pscustomobject]@{
        Name = $Name
        Healthy = $true
        Reason = "ok"
        AgeMinutes = [math]::Round($age,2)
    }
}

$awsStatus = Test-SyncLog -LogPath $AwsLog -Name "AWS" -SuccessPattern "Upserted AWS rows:" -CurrentTime $Now -MaxAgeMinutes $ThresholdMinutes
$gcpStatus = Test-SyncLog -LogPath $GcpLog -Name "GCP" -SuccessPattern "count=None|data=\[" -CurrentTime $Now -MaxAgeMinutes $ThresholdMinutes
$azureStatus = Test-SyncLog -LogPath $AzureLog -Name "Azure" -SuccessPattern "Azure upsert complete|count=None|data=\[" -CurrentTime $Now -MaxAgeMinutes $ThresholdMinutes

$statuses = @($awsStatus, $gcpStatus, $azureStatus)
$unhealthy = $statuses | Where-Object { -not $_.Healthy }

$statusLine = "[$($Now.ToString('yyyy-MM-dd HH:mm:ss'))] AWS=$($awsStatus.Reason), GCP=$($gcpStatus.Reason), Azure=$($azureStatus.Reason)"
Add-Content -Path $StatusLog -Value $statusLine
Write-Output $statusLine

if ($unhealthy.Count -gt 0) {
    $alertLine = "[$($Now.ToString('yyyy-MM-dd HH:mm:ss'))] ALERT: " + (($unhealthy | ForEach-Object { "$($_.Name): $($_.Reason)" }) -join "; ")
    Add-Content -Path $AlertLog -Value $alertLine
    Write-Error $alertLine
    exit 1
}

exit 0
