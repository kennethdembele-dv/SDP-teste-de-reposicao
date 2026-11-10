# Actualiza o indice e exporta o PDF a partir do Word.
# Uso: powershell -ExecutionPolicy Bypass -File docs\relatorio\exportar_pdf.ps1
param(
    [string]$Docx = (Join-Path $PSScriptRoot "..\Relatorio_Tecnico_Distributed-Buy.docx"),
    [string]$Pdf = (Join-Path $PSScriptRoot "..\Relatorio_Tecnico_Distributed-Buy.pdf")
)
$Docx = (Resolve-Path $Docx).Path
$Pdf = [System.IO.Path]::GetFullPath($Pdf)
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    $doc = $word.Documents.Open($Docx)
    # Estilos internos do indice (-20 = TOC 1, -21 = TOC 2): linhas compactas para caber numa pagina.
    foreach ($id in -20, -21) {
        $estilo = $doc.Styles.Item($id)
        $estilo.Font.Name = "Calibri"
        $estilo.Font.Size = 10
        $estilo.ParagraphFormat.SpaceBefore = 0
        $estilo.ParagraphFormat.SpaceAfter = 1
        $estilo.ParagraphFormat.LineSpacingRule = 0
    }
    $doc.TablesOfContents.Item(1).Update()
    $doc.Fields.Update() | Out-Null
    $doc.Repaginate()
    $doc.TablesOfContents.Item(1).UpdatePageNumbers()
    $doc.Save()
    $doc.ExportAsFixedFormat($Pdf, 17)
    "paginas: " + $doc.ComputeStatistics(2)
    $doc.Close()
} finally {
    $word.Quit()
}
$Pdf
