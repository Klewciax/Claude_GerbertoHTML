import { useEffect, useState } from 'react'

export function useSvgImage(svg: string | undefined): HTMLImageElement | null {
  const [image, setImage] = useState<HTMLImageElement | null>(null)

  useEffect(() => {
    if (!svg) {
      setImage(null)
      return
    }

    const blob = new Blob([svg], { type: 'image/svg+xml' })
    const url = URL.createObjectURL(blob)
    const img = new Image()
    img.onload = () => setImage(img)
    img.onerror = () => setImage(null)
    img.src = url

    return () => {
      URL.revokeObjectURL(url)
    }
  }, [svg])

  return image
}
