import { read, plot, renderLayers, renderBoard, stringifySvg } from '@tracespace/core'
import type { GerberRenderResult, ViewBoxTuple } from '../types'

function parseViewBox(svg: string): ViewBoxTuple | undefined {
  const match = svg.match(/viewBox="([-\d.eE]+)\s+([-\d.eE]+)\s+([-\d.eE]+)\s+([-\d.eE]+)"/)
  if (!match) return undefined
  const [, x, y, width, height] = match
  return { x: Number(x), y: Number(y), width: Number(width), height: Number(height) }
}

export async function renderGerberFiles(files: File[]): Promise<GerberRenderResult> {
  const warnings: string[] = []

  if (files.length === 0) {
    return { warnings: ['Nie wybrano żadnych plików Gerber.'] }
  }

  try {
    const readResult = await read(files)

    if (readResult.layers.length === 0) {
      return { warnings: ['Żaden z wybranych plików nie został rozpoznany jako plik Gerber/Excellon.'] }
    }

    const unresolved = readResult.layers.filter((layer) => !layer.type)
    if (unresolved.length > 0) {
      warnings.push(
        `Nie rozpoznano typu warstwy dla: ${unresolved.map((l) => l.filename).join(', ')}. Plik został zignorowany przy renderowaniu.`,
      )
    }

    const plotResult = plot(readResult)
    if (plotResult.boardShape.failureReason) {
      warnings.push(
        'Nie znaleziono zamkniętego konturu płytki (warstwa Outline/Edge.Cuts) — obrys PCB może być niewidoczny, ale warstwy miedzi i opisu powinny się wyrenderować.',
      )
    }

    const renderLayersResult = renderLayers(plotResult)
    const board = renderBoard(renderLayersResult)

    const topSvg = board.top ? stringifySvg(board.top) : undefined
    const bottomSvg = board.bottom ? stringifySvg(board.bottom) : undefined
    const viewBox = topSvg ? parseViewBox(topSvg) : bottomSvg ? parseViewBox(bottomSvg) : undefined

    if (!topSvg && !bottomSvg) {
      warnings.push('Renderowanie nie zwróciło żadnej grafiki SVG dla żadnej ze stron płytki.')
    }

    return { topSvg, bottomSvg, viewBox, warnings }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    return {
      warnings: [`Błąd podczas renderowania plików Gerber: ${message}. Sprawdź, czy pliki są w formacie RS-274X/Excellon.`],
    }
  }
}

export function svgToDataUrl(svg: string): string {
  const encoded = encodeURIComponent(svg)
    .replace(/'/g, '%27')
    .replace(/"/g, '%22')
  return `data:image/svg+xml;charset=utf-8,${encoded}`
}
