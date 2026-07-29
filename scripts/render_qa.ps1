$ErrorActionPreference = "Stop"
$ppt = "D:\ai_code\huoshangbei002\docs\qa_render.pptx"
$out = "D:\ai_code\huoshangbei002\docs\qa_preview"
New-Item -ItemType Directory -Force -Path $out | Out-Null
$app = New-Object -ComObject PowerPoint.Application
$app.Visible = -1
$pres = $app.Presentations.Open($ppt, $false, $false, $false)
$pres.Export($out, "PNG", 1920, 1080)
$pres.Close()
$app.Quit()
[System.Runtime.Interopservices.Marshal]::ReleaseComObject($pres) | Out-Null
[System.Runtime.Interopservices.Marshal]::ReleaseComObject($app) | Out-Null
Write-Host "RENDER_DONE"
