import { useEffect, useState } from 'react'
import { useAuth } from './auth'

type Props = {
  path: string
  alt: string
  className?: string
}

export function PrivateImage({ path, alt, className }: Props) {
  const { apiBlob } = useAuth()
  const [source, setSource] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    let objectUrl = ''
    setSource('')
    setError('')
    apiBlob(path).then((blob) => {
      if (!active) return
      objectUrl = URL.createObjectURL(blob)
      setSource(objectUrl)
    }).catch((cause) => {
      if (active) setError(cause instanceof Error ? cause.message : 'Không tải được hình ảnh.')
    })
    return () => {
      active = false
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [apiBlob, path])

  if (error) return <span role="alert">{error}</span>
  if (!source) return <span role="status">Đang tải hình ảnh…</span>
  return <img src={source} alt={alt} className={className} />
}
