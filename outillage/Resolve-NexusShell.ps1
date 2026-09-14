<# 
.SYNOPSIS
    Resolve the PowerShell interpreter path, preferring the stable WindowsApps alias.

.DESCRIPTION
    Measure performed on 2026‑09‑13 (code 0x80070002) revealed that the
    scheduled‑task registration scripts stored the version‑specific Store path
    (e.g. `…\Microsoft.PowerShell_7.6.5.0_…\pwsh.exe`).  
    After an auto‑update the version folder disappears, causing the tasks
    to fail with **LastTaskResult 0x80070002** (file not found).  

    The alias `$env:LOCALAPPDATA\Microsoft\WindowsApps\pwsh.exe` is a
    *stable* indirection that never changes between Store updates, therefore
    this function returns it when the resolved path matches the Store pattern
    **and** the alias file exists.  
    No side‑effects are introduced; the function is only defined when the file
    is dot‑sourced.
#>

function Resolve-NexusShell {
    param(
        [string]$Candidat
    )

    # --------------------------------------------------------------------
    # 1️⃣  Resolve candidate when none is supplied
    # --------------------------------------------------------------------
    if ([string]::IsNullOrWhiteSpace($Candidat)) {
        $candidate = (Get-Command pwsh -ErrorAction SilentlyContinue).Source
        if (-not $candidate) {
            $candidate = (Get-Command powershell -ErrorAction SilentlyContinue).Source
        }
    } else {
        $candidate = $Candidat
    }

    # --------------------------------------------------------------------
    # 2️⃣  Nothing found → return $null (do not throw)
    # --------------------------------------------------------------------
    if ($null -eq $candidate) {
        return $null
    }

    # --------------------------------------------------------------------
    # 3️⃣  If the path is a version‑specific Store location and the stable
    #     alias exists, return the alias.
    # --------------------------------------------------------------------
    $storePattern = '\\WindowsApps\\Microsoft\.PowerShell_[0-9\.]+_'
    $aliasPath    = Join-Path $env:LOCALAPPDATA 'Microsoft\WindowsApps\pwsh.exe'

    if ($candidate -match $storePattern -and (Test-Path $aliasPath)) {
        return $aliasPath
    }

    # --------------------------------------------------------------------
    # 4️⃣  Otherwise return the resolved path unchanged.
    # --------------------------------------------------------------------
    return $candidate
}
