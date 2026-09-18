<#
.SYNOPSIS
    Resolve the PowerShell interpreter path for a scheduled task, rejecting
    broken Store aliases and version-pinned paths when a real binary exists.

.DESCRIPTION
    History and rationale
    ---------------------
    On 2026-09-13 the scheduled-task registration scripts wrote the
    version-specific PowerShell 7 Store path, e.g.
    "...\WindowsApps\Microsoft.PowerShell_7.6.5.0_8wekyb3d8bbwe\pwsh.exe".
    After an automatic Store update that version folder disappears and the
    tasks fail with LastTaskResult 0x80070002 (file not found).

    The first fix was to substitute the per-user alias
    "$env:LOCALAPPDATA\Microsoft\WindowsApps\pwsh.exe", presented as a stable
    indirection. Measure on 2026-09-17 shows that alias is not a real binary:
    it is a reparse point of size zero, an execution alias re-exec'd by the
    App Execution Alias service. Under the S4U context of a scheduled task,
    with no interactive session, that indirection does not resolve and the
    task fails with LastTaskResult 0x80070005 (access denied). So the
    "remedy" merely swapped one failure for a nearby one.

    Therefore this resolver no longer returns that alias. It tests every
    candidate for two properties that distinguish a real binary from a
    Store alias or empty stub:

      * the file must NOT carry the ReparsePoint attribute, and
      * the file size must be greater than zero.

    Preference order
    ----------------
    1. A real, non version-pinned pwsh.exe if one exists
       (e.g. "C:\Program Files\PowerShell\7\pwsh.exe"). When a candidate is
       supplied it is validated against the same rules.
    2. The system Windows PowerShell binary
       "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe", whose
       path is stable across updates and which is a real executable.
    3. As a last resort, the version-specific Store path
       "...\WindowsApps\Microsoft.PowerShell_<ver>_<id>\pwsh.exe". If this
       path is retained, the function emits a Write-Warning stating that
       the path will break on the next Store update; the caller must accept
       that risk or refuse to register the task.

    The function returns $null when no acceptable candidate is found; it
    never throws. The decision to refuse registering a task belongs to the
    caller. Importing this file has no side effects: the function is only
    DEFINED when the file is dot-sourced.

    Output channel
    --------------
    All messages are written in pure ASCII. Scheduled tasks that consume
    this resolver often run in code pages that are not UTF-8; non-ASCII
    characters would be mangled.
#>

function Resolve-NexusShell {
    [CmdletBinding()]
    param(
        [string]$Candidat
    )

    # --------------------------------------------------------------------
    # 1. Build the list of candidates to consider.
    # --------------------------------------------------------------------
    $candidates = New-Object System.Collections.Generic.List[string]

    if (-not [string]::IsNullOrWhiteSpace($Candidat)) {
        $candidates.Add($Candidat) | Out-Null
    }

    $fromCmd = (Get-Command pwsh -ErrorAction SilentlyContinue).Source
    if ($fromCmd) { $candidates.Add($fromCmd) | Out-Null }

    $systemPwsh = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    if (Test-Path -LiteralPath $systemPwsh) {
        $candidates.Add($systemPwsh) | Out-Null
    }

    # Stable, non version-pinned PowerShell 7 install location, if present.
    $stablePwsh7 = Join-Path ${env:ProgramFiles} 'PowerShell\7\pwsh.exe'
    if (Test-Path -LiteralPath $stablePwsh7) {
        # Place it ahead of the system binary so a real pwsh wins.
        $candidates.Insert(0, $stablePwsh7) | Out-Null
    }

    # --------------------------------------------------------------------
    # 2. Validate each candidate.
    #    Reject any path whose file carries the ReparsePoint attribute or
    #    whose size is zero. Those two properties identify Store execution
    #    aliases and empty stubs, which do not work under S4U.
    # --------------------------------------------------------------------
    $storePattern = '\\WindowsApps\\Microsoft\.PowerShell_[0-9]+(\.[0-9]+)+_[^\\]+\\pwsh\.exe$'

    $versionedFallback = $null

    foreach ($path in $candidates) {
        if ([string]::IsNullOrWhiteSpace($path)) { continue }
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { continue }

        $item = Get-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
        if ($null -eq $item) { continue }

        $isReparse = ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0
        $isEmpty   = ($item.Length -le 0)

        if ($isReparse -or $isEmpty) {
            continue
        }

        # ----------------------------------------------------------------
        # 3. The version-specific Store path is acceptable only as a last
        #    resort, and the caller must be warned.
        # ----------------------------------------------------------------
        if ($path -match $storePattern) {
            if ($null -eq $versionedFallback) { $versionedFallback = $path }
            continue
        }

        return $path
    }

    if ($null -ne $versionedFallback) {
        $warningMessage = ("Resolve-NexusShell: retaining version-specific Store path '{0}'. " -f $versionedFallback) +
                          "This path is tied to the installed Store version and will break on the next PowerShell 7 update."
        Write-Warning $warningMessage
        return $versionedFallback
    }

    # --------------------------------------------------------------------
    # 4. Nothing acceptable found. Return $null; do not throw.
    # --------------------------------------------------------------------
    return $null
}
