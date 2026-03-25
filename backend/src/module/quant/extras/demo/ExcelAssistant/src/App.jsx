import React, { useRef, useEffect, useState, useCallback } from 'react'
import jspreadsheet from 'jspreadsheet-ce'
import ExcelJS from 'exceljs/dist/exceljs.min.js'
import * as XLSX from 'xlsx'
import 'jspreadsheet-ce/dist/jspreadsheet.css'
import 'jsuites/dist/jsuites.css'
import './App.css'
import ChatSidebar from './ChatSidebar'

const FONT_FALLBACKS = {
  'Calibri': ['"Carlito"', '"Inter"', '"Noto Sans"', '"Helvetica Neue"', 'Arial', 'sans-serif'],
  'Segoe UI': ['"Inter"', '"Noto Sans"', '"Helvetica Neue"', 'Arial', 'sans-serif'],
}

const DEFAULT_FONT_FALLBACKS = ['"Inter"', '"Noto Sans"', '"Helvetica Neue"', 'Arial', 'sans-serif']
const PX_PER_POINT = 4 / 3
const PT_PER_PX = 1 / PX_PER_POINT

function toFixedNumber(value, decimals = 2) {
  if (!Number.isFinite(value)) return null
  const factor = 10 ** decimals
  return Math.round(value * factor) / factor
}

function ptToPx(sizePt) {
  if (!Number.isFinite(sizePt)) return null
  return toFixedNumber(sizePt * PX_PER_POINT)
}

function pxToPt(sizePx) {
  if (!Number.isFinite(sizePx)) return null
  return toFixedNumber(sizePx * PT_PER_PX)
}

function parseCssFontSize(value) {
  if (!value) return null
  const normalized = `${value}`.trim()
  const numeric = parseFloat(normalized)
  if (Number.isNaN(numeric)) return null
  const isPt = normalized.toLowerCase().endsWith('pt')
  return isPt ? ptToPx(numeric) : numeric
}

function formatPx(sizePx) {
  if (!Number.isFinite(sizePx)) return ''
  const rounded = toFixedNumber(sizePx)
  if (rounded === null) return ''
  return `${Number.isInteger(rounded) ? Math.trunc(rounded) : rounded}`
}

function normalizeFontName(name = '') {
  return name.replace(/^['"]|['"]$/g, '').trim()
}

function buildFontFamily(name) {
  const primary = normalizeFontName(name) || 'Segoe UI'
  const fallbacks = FONT_FALLBACKS[primary] || DEFAULT_FONT_FALLBACKS
  const primaryToken = /\s/.test(primary) ? `"${primary}"` : primary
  const seen = new Set()
  return [primaryToken, ...fallbacks].filter(part => {
    const key = part.toLowerCase()
    if (seen.has(key)) return false
    seen.add(key)
    return true
  }).join(', ')
}

// API base URL - empty string since we use Vite proxy in development
const API_BASE_URL = ''

// Convert XLSX color object to CSS hex color
function xlsxColorToCSS(color) {
  if (!color) return null
  const rgb = color.rgb || color.RGB
  if (!rgb) return null
  const hex = rgb.length === 8 ? rgb.slice(2) : rgb
  return `#${hex.slice(-6)}`
}

// Convert CSS hex color to XLSX color object
function cssColorToXlsx(color) {
  if (!color) return null
  let normalized = color.trim()
  if (normalized.startsWith('#')) normalized = normalized.slice(1)
  if (normalized.length === 3) {
    normalized = normalized
      .split('')
      .map(ch => ch + ch)
      .join('')
  }
  if (normalized.length !== 6) return null
  return { rgb: `FF${normalized.toUpperCase()}` }
}

// Parse XLSX style object into CSS string
function styleObjectToCss(styleObj) {
  if (!styleObj) return ''
  const css = []
  const { font, fill } = styleObj

  if (font) {
    if (font.color) {
      const color = xlsxColorToCSS(font.color)
      if (color) css.push(`color: ${color}`)
    }
    if (font.name) css.push(`font-family: ${buildFontFamily(font.name)}`)
    if (font.sz) {
      const pxSize = ptToPx(font.sz)
      if (pxSize !== null) css.push(`font-size: ${formatPx(pxSize)}px`)
    }
    if (font.bold) css.push('font-weight: bold')
    if (font.italic) css.push('font-style: italic')
  }

  if (fill?.fgColor || fill?.bgColor) {
    const bg = xlsxColorToCSS(fill.fgColor || fill.bgColor)
    if (bg) css.push(`background-color: ${bg}`)
  }

  return css.join('; ')
}

// Parse CSS string into XLSX style object
function cssToXlsxStyle(cssString) {
  if (!cssString) return null
  const style = {}
  cssString
    .split(';')
    .map(part => part.trim())
    .filter(Boolean)
    .forEach(part => {
      const [prop, value] = part.split(':').map(p => p && p.trim())
      if (!prop || !value) return
      switch (prop) {
        case 'color':
          style.font = style.font || {}
          style.font.color = cssColorToXlsx(value)
          break
        case 'background-color':
          style.fill = {
            patternType: 'solid',
            fgColor: cssColorToXlsx(value),
            bgColor: cssColorToXlsx(value),
          }
          break
        case 'font-family':
          style.font = style.font || {}
          style.font.name = value
          break
        case 'font-size':
          style.font = style.font || {}
          {
            const sizePx = parseCssFontSize(value)
            const sizePt = pxToPt(sizePx ?? NaN)
            if (sizePt !== null) {
              style.font.sz = sizePt
            }
          }
          break
        case 'font-weight':
          style.font = style.font || {}
          style.font.bold = value === 'bold' || value === '700'
          break
        case 'font-style':
          style.font = style.font || {}
          style.font.italic = value === 'italic'
          break
        default:
          break
      }
    })

  return Object.keys(style).length ? style : null
}

function parseStyleString(styleString = '') {
  return styleString
    .split(';')
    .map(part => part.trim())
    .filter(Boolean)
    .reduce((acc, part) => {
      const [prop, value] = part.split(':').map(p => p && p.trim())
      if (prop && value) acc[prop] = value
      return acc
    }, {})
}

function mergeStyleStrings(existing = '', updates = {}) {
  const merged = { ...parseStyleString(existing) }
  Object.entries(updates).forEach(([key, value]) => {
    merged[key] = value
  })
  return Object.entries(merged)
    .map(([k, v]) => `${k}: ${v}`)
    .join('; ')
}

// ExcelJS color (argb) -> CSS hex
function excelColorToCss(argb) {
  if (!argb) return null
  const hex = argb.slice(-6)
  return `#${hex}`
}

// ExcelJS font/fill -> CSS string
function excelCellStyleToCss(cell) {
  const css = []
  const { font, fill } = cell

  if (font) {
    if (font.color?.argb) {
      const color = excelColorToCss(font.color.argb)
      if (color) css.push(`color: ${color}`)
    }
    if (font.name) css.push(`font-family: ${buildFontFamily(font.name)}`)
    if (font.size) {
      const pxSize = ptToPx(font.size)
      if (pxSize !== null) css.push(`font-size: ${formatPx(pxSize)}px`)
    }
    if (font.bold) css.push('font-weight: bold')
    if (font.italic) css.push('font-style: italic')
  }

  if (fill && fill.type === 'pattern') {
    const fg = fill.fgColor?.argb
    const bg = fill.bgColor?.argb
    const color = excelColorToCss(fg || bg)
    if (color) css.push(`background-color: ${color}`)
  }

  return css.join('; ')
}

// CSS string -> ExcelJS style parts
function cssToExcelStyle(cssString) {
  if (!cssString) return {}
  const parsed = parseStyleString(cssString)
  const font = {}
  let hasFont = false
  let fill = null

  if (parsed.color) {
    font.color = { argb: `FF${parsed.color.replace('#', '').padStart(6, '0').toUpperCase()}` }
    hasFont = true
  }
  if (parsed['font-family']) {
    const [primaryFont] = parsed['font-family'].split(',')
    font.name = normalizeFontName(primaryFont)
    hasFont = true
  }
  if (parsed['font-size']) {
    const sizePx = parseCssFontSize(parsed['font-size'])
    if (sizePx !== null) {
      const sizePt = pxToPt(sizePx)
      if (sizePt !== null) {
        font.size = sizePt
        hasFont = true
      }
    }
  }
  if (parsed['font-weight']) {
    font.bold = parsed['font-weight'] === 'bold' || parsed['font-weight'] === '700'
    hasFont = true
  }
  if (parsed['font-style']) {
    font.italic = parsed['font-style'] === 'italic'
    hasFont = true
  }

  const bg = parsed['background-color']
  if (bg) {
    fill = {
      type: 'pattern',
      pattern: 'solid',
      fgColor: { argb: `FF${bg.replace('#', '').padStart(6, '0').toUpperCase()}` },
    }
  }

  return {
    font: hasFont ? font : undefined,
    fill: fill || undefined,
  }
}

function applyStyleToCellDom(instance, cellAddress, styleString) {
  if (!instance || !cellAddress || !styleString) return
  const { r, c } = XLSX.utils.decode_cell(cellAddress)
  const cellEl = instance.getCellFromCoords?.(c, r)
  if (cellEl) {
    const merged = mergeStyleStrings(cellEl.getAttribute('style') || '', parseStyleString(styleString))
    cellEl.setAttribute('style', merged)
  }
}

function applyAllStylesToDom(instance, styles = {}) {
  if (!instance || !styles) return
  Object.entries(styles).forEach(([cellAddress, styleString]) => {
    applyStyleToCellDom(instance, cellAddress, styleString)
  })
}

function applyStylesAfterRender(instance, styles = {}) {
  if (!instance) return
  const applyNow = () => applyAllStylesToDom(instance, styles)
  // Allow the table to finish rendering before applying styles
  if (typeof window !== 'undefined' && window.requestAnimationFrame) {
    requestAnimationFrame(() => requestAnimationFrame(applyNow))
  } else {
    setTimeout(applyNow, 10)
  }
}

// Extract data and styles from workbook buffer preserving formulas and styling
async function extractDataAndStyles(arrayBuffer) {
  const workbook = new ExcelJS.Workbook()
  await workbook.xlsx.load(arrayBuffer)
  const worksheet = workbook.worksheets[0]

  const maxRow = worksheet.rowCount || 0
  let maxCol = 0

  worksheet.eachRow({ includeEmpty: true }, (row) => {
    maxCol = Math.max(maxCol, row.cellCount)
  })

  const rows = Math.max(maxRow, 1)
  const cols = Math.max(maxCol, 1)
  const data = Array.from({ length: rows }, () => Array.from({ length: cols }, () => ''))
  const styles = {}

  for (let r = 1; r <= rows; r++) {
    const row = worksheet.getRow(r)
    for (let c = 1; c <= cols; c++) {
      const cell = row.getCell(c)
      const address = XLSX.utils.encode_cell({ r: r - 1, c: c - 1 })

      const v = cell.value
      const formula =
        cell.formula ||
        (v && typeof v === 'object' && 'formula' in v && v.formula) ||
        (v && typeof v === 'object' && 'sharedFormula' in v && v.sharedFormula)

      let displayValue = ''
      if (formula) {
        displayValue = `=${formula}`
      } else if (v !== null && v !== undefined) {
        if (v && typeof v === 'object') {
          if (Array.isArray(v.richText)) {
            displayValue = v.richText.map(part => part.text || '').join('')
          } else if ('hyperlink' in v) {
            displayValue = v.text || v.hyperlink || ''
          } else if ('result' in v && v.result !== undefined) {
            displayValue = v.result
          } else {
            displayValue = cell.text || ''
          }
        } else if (v instanceof Date) {
          displayValue = cell.text || v.toISOString()
        } else {
          displayValue = v
        }
      }

      data[r - 1][c - 1] = displayValue === undefined || displayValue === null ? '' : displayValue

      const css = excelCellStyleToCss(cell)
      if (css) styles[address] = css
    }
  }

  return { data, styles }
}

// Convert spreadsheet data plus styles to ExcelJS workbook buffer
async function dataToExcelBuffer(data, styles = {}) {
  const workbook = new ExcelJS.Workbook()
  const worksheet = workbook.addWorksheet('Sheet1')

  data.forEach((row, rowIndex) => {
    row.forEach((cellValue, colIndex) => {
      const cell = worksheet.getCell(rowIndex + 1, colIndex + 1)
      const cellStr = String(cellValue ?? '')
      if (cellStr.startsWith('=')) {
        cell.value = { formula: cellStr.substring(1) }
      } else {
        const num = Number(cellValue)
        if (!Number.isNaN(num) && cellStr.trim() !== '') {
          cell.value = num
        } else {
          cell.value = cellValue
        }
      }

      const style = cssToExcelStyle(styles[XLSX.utils.encode_cell({ r: rowIndex, c: colIndex })])
      if (style.font) cell.font = style.font
      if (style.fill) cell.fill = style.fill
    })
  })

  return workbook.xlsx.writeBuffer()
}

function App() {
  const spreadsheetRef = useRef(null)
  const jspreadsheetInstance = useRef(null)
  const fileInputRef = useRef(null)
  const stylesRef = useRef({})
  const [fileName, setFileName] = useState('spreadsheet.xlsx')
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [selectedRange, setSelectedRange] = useState(null)
  const [textColor, setTextColor] = useState('#000000')
  const [fillColor, setFillColor] = useState('#ffffff')
  const [fontFamily, setFontFamily] = useState('Arial')
  const [fontSize, setFontSize] = useState(12)
  const [isBold, setIsBold] = useState(false)
  const [isItalic, setIsItalic] = useState(false)

  const initSpreadsheet = (data = [[]], styles = {}) => {
    if (jspreadsheetInstance.current) {
      jspreadsheet.destroy(spreadsheetRef.current)
    }

    stylesRef.current = styles || {}
    setSelectedRange(null)
    jspreadsheetInstance.current = jspreadsheet(spreadsheetRef.current, {
      data: data,
      style: stylesRef.current,
      minDimensions: [50, 100], // Increased dimensions for better scrolling experience
      tableOverflow: true,
      tableWidth: '100%',
      tableHeight: '100%',
      columnDrag: true,
      rowDrag: true,
      allowInsertRow: true,
      allowInsertColumn: true,
      allowDeleteRow: true,
      allowDeleteColumn: true,
      allowRenameColumn: true,
      columnResize: true,
      rowResize: true,
      contextMenu: true,
      defaultColWidth: 100,
      search: true, // Enable search
      pagination: false, // Infinite scroll behavior
      onselection: (_, x1, y1, x2, y2) => {
        setSelectedRange({ x1, y1, x2, y2 })
      },
      onload: () => applyStylesAfterRender(jspreadsheetInstance.current, stylesRef.current),
    })
    applyStylesAfterRender(jspreadsheetInstance.current, stylesRef.current)
  }

  // Initialize empty spreadsheet on mount
  useEffect(() => {
    if (spreadsheetRef.current && !jspreadsheetInstance.current) {
      initSpreadsheet()
    }

    return () => {
      if (jspreadsheetInstance.current) {
        jspreadsheet.destroy(spreadsheetRef.current)
        jspreadsheetInstance.current = null
      }
    }
  }, [])

  // Handle XLSX file upload
  const handleUpload = async (event) => {
    const file = event.target.files[0]
    if (!file) return

    setFileName(file.name)
    try {
      const buffer = await file.arrayBuffer()
      const { data: spreadsheetData, styles } = await extractDataAndStyles(buffer)
      initSpreadsheet(spreadsheetData, styles)
      applyStylesAfterRender(jspreadsheetInstance.current, stylesRef.current)
    } catch (error) {
      console.error('Error reading file:', error)
      alert('Error reading file. Please make sure it is a valid Excel file.')
    } finally {
      event.target.value = ''
    }
  }

  // Load Excel file from array buffer
  const loadFromArrayBuffer = useCallback(async (arrayBuffer) => {
    try {
      const { data: spreadsheetData, styles } = await extractDataAndStyles(arrayBuffer)
      initSpreadsheet(spreadsheetData, styles)
      applyStylesAfterRender(jspreadsheetInstance.current, stylesRef.current)
    } catch (error) {
      console.error('Error loading file:', error)
      throw error
    }
  }, [])

  // Handle XLSX download
  const handleDownload = async () => {
    if (!jspreadsheetInstance.current) {
      alert('No spreadsheet data to download')
      return
    }

    try {
      const data = jspreadsheetInstance.current.getData()
      const buffer = await dataToExcelBuffer(data, stylesRef.current)
      const blob = new Blob([buffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
      const link = document.createElement('a')
      link.href = URL.createObjectURL(blob)
      link.download = fileName.endsWith('.xlsx') ? fileName : `${fileName}.xlsx`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(link.href)
    } catch (error) {
      console.error('Error downloading file:', error)
      alert('Error generating file for download.')
    }
  }

  // Get current spreadsheet as Blob
  const getSpreadsheetAsBlob = useCallback(async () => {
    if (!jspreadsheetInstance.current) {
      throw new Error('No spreadsheet data')
    }

    const data = jspreadsheetInstance.current.getData()
    const buffer = await dataToExcelBuffer(data, stylesRef.current)
    return new Blob([buffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
  }, [fileName])

  // Handle sending message to AI agent
  const handleSendMessage = useCallback(async (message, history) => {
    setIsLoading(true)
    
    try {
      // Get current spreadsheet as blob
      const blob = await getSpreadsheetAsBlob()
      
      // Create form data
      const formData = new FormData()
      formData.append('message', message)
      formData.append('file', blob, 'input.xlsx')
      formData.append('history', JSON.stringify(history))
      
      // Send to API
      const response = await fetch(`${API_BASE_URL}/api/chat`, {
        method: 'POST',
        body: formData,
      })
      
      const result = await response.json()
      
      if (result.success) {
        // Download the modified file and load it
        const fileResponse = await fetch(`${API_BASE_URL}${result.output_file}`)
        const arrayBuffer = await fileResponse.arrayBuffer()
        await loadFromArrayBuffer(arrayBuffer)
        
        // Clean up the file on the server
        if (result.session_id) {
          fetch(`${API_BASE_URL}/api/cleanup/${result.session_id}`, { method: 'DELETE' })
            .catch(() => {}) // Ignore cleanup errors
        }
      }
      
      return result
    } catch (error) {
      console.error('Error sending message:', error)
      return {
        success: false,
        error: error.message || 'Failed to communicate with AI agent. Make sure the server is running.',
      }
    } finally {
      setIsLoading(false)
    }
  }, [getSpreadsheetAsBlob, loadFromArrayBuffer])

  const handleNew = () => {
    setFileName('spreadsheet.xlsx')
    initSpreadsheet()
    stylesRef.current = {}
    setSelectedRange(null)
  }

  const toggleSidebar = () => {
    setSidebarOpen(prev => !prev)
  }

  const applyStyleToSelection = useCallback((styleUpdates) => {
    if (!jspreadsheetInstance.current || !selectedRange) {
      return
    }

    const startCol = Math.min(selectedRange.x1, selectedRange.x2)
    const endCol = Math.max(selectedRange.x1, selectedRange.x2)
    const startRow = Math.min(selectedRange.y1, selectedRange.y2)
    const endRow = Math.max(selectedRange.y1, selectedRange.y2)

    for (let row = startRow; row <= endRow; row++) {
      for (let col = startCol; col <= endCol; col++) {
        const cellAddress = XLSX.utils.encode_cell({ r: row, c: col })
    const normalizedUpdates = { ...styleUpdates }
    if (styleUpdates['font-family']) {
      normalizedUpdates['font-family'] = buildFontFamily(styleUpdates['font-family'])
    }

    const mergedStyle = mergeStyleStrings(stylesRef.current[cellAddress], normalizedUpdates)
        stylesRef.current[cellAddress] = mergedStyle
        applyStyleToCellDom(jspreadsheetInstance.current, cellAddress, mergedStyle)
      }
    }
  }, [selectedRange])

  const handleTextColorChange = (event) => {
    const color = event.target.value
    setTextColor(color)
    applyStyleToSelection({ color })
  }

  const handleFillColorChange = (event) => {
    const color = event.target.value
    setFillColor(color)
    applyStyleToSelection({ 'background-color': color })
  }

  const handleFontFamilyChange = (event) => {
    const family = event.target.value
    setFontFamily(family)
    applyStyleToSelection({ 'font-family': family })
  }

  const handleFontSizeChange = (event) => {
    const size = event.target.value
    setFontSize(size)
    if (size) {
      applyStyleToSelection({ 'font-size': `${size}px` })
    }
  }

  const handleToggleBold = () => {
    const next = !isBold
    setIsBold(next)
    applyStyleToSelection({ 'font-weight': next ? 'bold' : 'normal' })
  }

  const handleToggleItalic = () => {
    const next = !isItalic
    setIsItalic(next)
    applyStyleToSelection({ 'font-style': next ? 'italic' : 'normal' })
  }

  return (
    <div className={`app ${sidebarOpen ? 'sidebar-open' : ''}`}>
      <header className="header">
        <h1>Excel Assistant</h1>
      </header>

      <div className="toolbar">
        <button className="btn btn-primary" onClick={handleNew}>
          New
        </button>
        <button className="btn btn-secondary" onClick={() => fileInputRef.current?.click()}>
          Open
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".xlsx,.xls,.xlsm,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel,application/vnd.ms-excel.sheet.macroEnabled.12"
          onChange={handleUpload}
          style={{ display: 'none' }}
        />
        <button className="btn btn-success" onClick={handleDownload}>
          Save
        </button>

        <div className="formatting-controls">
          <select className="font-select" value={fontFamily} onChange={handleFontFamilyChange}>
            <option value="Arial">Arial</option>
            <option value="Calibri">Calibri</option>
            <option value="Segoe UI">Segoe UI</option>
            <option value="Times New Roman">Times New Roman</option>
            <option value="Courier New">Courier New</option>
            <option value="Verdana">Verdana</option>
          </select>
          <input
            className="font-size-input"
            type="number"
            min="8"
            max="72"
            value={fontSize}
            onChange={handleFontSizeChange}
          />
          <button
            className={`format-button ${isBold ? 'active' : ''}`}
            onClick={handleToggleBold}
            title="Toggle bold"
          >
            B
          </button>
          <button
            className={`format-button ${isItalic ? 'active' : ''}`}
            onClick={handleToggleItalic}
            title="Toggle italic"
          >
            I
          </button>
          <label className="color-control" title="Text color">
            <span>Text</span>
            <input type="color" value={textColor} onChange={handleTextColorChange} />
          </label>
          <label className="color-control" title="Fill color">
            <span>Fill</span>
            <input type="color" value={fillColor} onChange={handleFillColorChange} />
          </label>
        </div>

        <div className="file-name-container">
          <span>Editing:</span>
          <span className="file-name">{fileName}</span>
        </div>
      </div>

      <div className="spreadsheet-container">
        <div className="spreadsheet-wrapper">
          <div ref={spreadsheetRef}></div>
        </div>
      </div>

      <ChatSidebar
        isOpen={sidebarOpen}
        onToggle={toggleSidebar}
        onSendMessage={handleSendMessage}
        isLoading={isLoading}
      />
    </div>
  )
}

export default App
