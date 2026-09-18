import { read, plot, renderLayers, renderBoard, stringifySvg } from '@tracespace/core'

function parseViewBox(svg) {
  const match = svg.match(/viewBox="([-\d.eE]+)\s+([-\d.eE]+)\s+([-\d.eE]+)\s+([-\d.eE]+)"/)
  if (!match) return null
  const [, x, y, width, height] = match
  return { x: Number(x), y: Number(y), width: Number(width), height: Number(height) }
}

async function main() {
  const filePaths = process.argv.slice(2)
  const warnings = []

  if (filePaths.length === 0) {
    process.stdout.write(JSON.stringify({ warnings: ['Nie podano zadnych plikow Gerber.'] }))
    return
  }

  try {
    // In Node, tracespace's read() accepts plain file paths and reads them itself.
    const readResult = await read(filePaths)

    if (readResult.layers.length === 0) {
      process.stdout.write(
        JSON.stringify({ warnings: ['Zaden z plikow nie zostal rozpoznany jako Gerber/Excellon.'] }),
      )
      return
    }

    const unresolved = readResult.layers.filter((l) => !l.type)
    if (unresolved.length > 0) {
      warnings.push(
        `Nie rozpoznano typu warstwy dla: ${unresolved.map((l) => l.filename).join(', ')}.`,
      )
    }

    const plotResult = plot(readResult)
    if (plotResult.boardShape.failureReason) {
      warnings.push('Nie znaleziono zamknietego konturu plytki (Outline/Edge.Cuts).')
    }

    const renderLayersResult = renderLayers(plotResult)
    const board = renderBoard(renderLayersResult)

    const topSvg = board.top ? stringifySvg(board.top) : undefined
    const bottomSvg = board.bottom ? stringifySvg(board.bottom) : undefined
    const viewBox = topSvg ? parseViewBox(topSvg) : bottomSvg ? parseViewBox(bottomSvg) : null

    if (!topSvg && !bottomSvg) {
      warnings.push('Renderowanie nie zwrocilo grafiki SVG dla zadnej ze stron plytki.')
    }

    process.stdout.write(JSON.stringify({ topSvg, bottomSvg, viewBox, warnings }))
  } catch (error) {
    process.stdout.write(
      JSON.stringify({
        warnings: [`Blad podczas renderowania plikow Gerber: ${error && error.message ? error.message : String(error)}`],
      }),
    )
  }
}

main()
