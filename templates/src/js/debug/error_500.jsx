import React from 'react'
import { createRoot } from 'react-dom/client'
import '../../css/main.css'

function ServerErrorPage () {
  return (<div>Internal Server Error</div>)
}

createRoot(document.getElementById('app')).render(
  <ServerErrorPage/>
)
