import React from 'react'

export interface URLTreeProps {
  urls: object
}

export default function URLTree({ urls }: URLTreeProps) {
  return <div>{JSON.stringify(urls)}</div>
}
