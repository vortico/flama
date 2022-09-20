import React from 'react'
import { createRoot } from 'react-dom/client'
import '../../css/main.css'

function NotFoundErrorPage () {
  return (<div>URL Not Found</div>)
}

createRoot(document.getElementById('app')).render(
  <NotFoundErrorPage/>
)
