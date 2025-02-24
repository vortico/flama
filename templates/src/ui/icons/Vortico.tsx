import React from 'react'

export default function Vortico({ ...props }: React.ComponentProps<'svg'>) {
  return (
    <svg viewBox="0 0 1024 1024" xmlns="http://www.w3.org/2000/svg" {...props}>
      <path
        d="M341.49,413.75c-4.13,3.29-7.85,7.08-11.69,10.63-3.67,3.77-7.31,7.52-10.71,11.48-13.54,15.88-25.22,33.01-34.21,51.46-18.33,36.64-27.95,76.95-29.36,116.91-.64,19.99,.85,39.91,4.29,59.3,3.76,19.34,9.4,38.15,17.34,55.83,7.83,17.71,18.02,34.17,30.16,49.5,12.02,15.37,25.79,29.57,40.97,42.3,15.05,12.88,31.44,24.38,48.76,34.48,17.22,10.29,35.46,19.01,54.23,26.65,18.76,7.69,38.19,13.94,57.97,19.23,19.85,5.05,40.06,9.06,60.53,12.06,20.48,3,41.23,4.61,62.11,5.66,20.89,.87,41.91,.7,63.02-.11,21.08-1.09,42.29-2.61,63.49-5.17,21.26-2.26,125.44-27.98,33.77,3.27-10.2,3.64-20.42,7.38-30.83,10.52-20.71,6.81-41.99,11.73-63.46,16.19-21.55,3.99-43.37,7.12-65.41,8.72-5.5,.51-11.03,.67-16.56,.93-5.53,.27-11.07,.48-16.62,.43-5.55,0-11.1,.12-16.66,.01l-16.68-.66c-44.48-2.39-89.13-10.67-131.81-26.02-21.35-7.61-42.13-17.1-62.13-28.2-19.9-11.28-38.93-24.35-56.6-39.25-17.54-15.05-33.78-31.87-47.88-50.57-13.9-18.74-26.19-39.3-34.7-61.32-8.61-21.93-14.47-44.79-17.21-67.89-2.73-23.1-2.51-46.35,.21-69.14,5.74-45.52,21.81-89.49,47.76-126.49,19.27-27.67,45.15-50.46,73.59-67.06,15.58-9.09,12.19-.88,4.33,6.3Z"
        fill="#e05922"
      />
      <path
        d="M459.32,516.03c4.44-3.84,10.57,1.79,7.52,6.81-4.99,8.18-7.54,17.19-6.95,25.72,.51,8.41,3.67,15.98,8.7,22.02,4.93,5.69,11.76,10.38,19.26,13.32,15.06,6.17,31.86,5.47,44.44-.91,12.66-6.28,23.08-18.15,28.39-31.95,5.51-13.78,5.92-28.56,1.92-41.61-1.95-6.6-5.4-12.76-9.53-18.72l-1.51-2.25-1.65-1.92-1.6-1.95-1.88-1.88c-1.19-1.28-2.47-2.53-3.91-3.69-1.37-1.2-2.7-2.43-4.26-3.48-11.78-9.12-26.26-15.18-40.74-17.29-7.29-.85-14.59-1.1-21.9-.32-1.83,.23-3.64,.65-5.47,.93l-2.74,.44-2.71,.76-5.19,1.38c-.17,.05-.34,.1-.51,.16l-5.12,1.95c-14.45,5.37-27.44,13.84-37.15,25.22-10.01,11.1-17.29,24.81-21.02,39.89-3.75,15.11-3.76,31.41-.7,47.65,1.48,8.14,4.12,16.18,7.32,24.12,2.98,7.83,6.67,14.57,11.45,21.26,18.93,26.56,53.25,45,90.6,51.63,18.72,3.52,38.35,4.07,57.9,1.5,9.88-1.38,19.8-3.54,29.53-6.75,5.52-1.82,9.38,5.57,4.65,8.96-8.94,6.4-18.81,11.76-29.12,16-20.39,8.5-42.63,12.95-65.24,13.53-22.6,.48-45.76-2.69-68.01-10.85-11.16-3.97-22-9.31-32.32-15.87-10.29-6.58-20.16-14.38-28.69-23.73-8.53-9.18-16.21-19.97-21.97-30.92-5.74-10.74-10.56-22.15-14.02-34.12-7.19-23.87-8.8-49.99-4.32-75.53,4.59-25.55,16.38-50.09,33.24-70.47,17-20.42,39.62-35.63,63.87-44.89l9.02-3.2c.14-.05,.28-.09,.42-.13l9.38-2.44,4.81-1.18,4.93-.81c3.3-.5,6.57-1.09,9.89-1.45,13.33-1.25,26.85-.88,40.07,1.34,26.3,5.06,51,16.33,70.94,33.99,2.56,2.1,4.94,4.49,7.31,6.88,2.41,2.31,4.69,4.83,6.88,7.48l3.18,3.77c.08,.09,.15,.19,.22,.29l2.99,4.1,2.92,4.11c.08,.11,.15,.22,.22,.34l2.5,4.17c6.99,11.47,12.28,24.45,14.99,38.08,2.75,13.59,3.16,27.69,.94,41.21-2.22,13.53-6.8,26.43-13.32,38.13-6.47,11.72-15.09,22.19-25.47,30.81-10.17,8.62-22.47,15.42-35.6,19.14-13.12,3.76-26.95,4.55-39.89,2.27-12.95-2.27-25.1-7.13-35.66-14.31-10.47-7.25-19.72-16.64-25.64-28.65-5.59-11.7-7.51-25.35-4.7-37.54,1.25-6.13,3.74-11.79,6.69-16.94,3.23-5.02,6.85-9.61,11.16-13.36,.09-.07,.17-.15,.26-.22Z"
        fill="#018080"
      />
      <path
        d="M98.42,646.77l.07-16.47,.52-16.51c1.03-22.04,3.8-44.08,8.11-65.99,8.71-43.73,24.57-87.01,49.25-125.97,24.47-38.99,58.12-73.12,97.84-98.05,19.84-12.47,41.14-22.6,63.18-30.52,22.13-7.67,44.99-13.18,68.18-16.14,46.35-5.78,94-2.55,139.16,12.63,11.27,3.81,22.39,8.57,33.11,14.01,10.64,5.57,20.7,11.96,30.36,18.8,9.61,6.92,18.64,14.52,27.17,22.58,8.41,8.19,16.39,16.76,23.76,25.83,29.1,36.36,48.92,80.72,52.58,126.94,1.85,23.01-.5,46.21-7.07,67.84-6.51,21.64-22.14,38.76-19.52,28.34,3.07-10.23,4.93-20.71,6.18-31.1,1.03-10.45,1.32-20.85,.77-31.14-.86-10.29-1.86-20.48-4.35-30.41-9.05-39.83-30.33-75.81-58.1-104.69-27.76-29.04-62.14-50.98-99.26-61.61-37.74-10.7-78.7-12.91-118.28-7.67-39.65,5.17-78.28,17.85-112.81,37.81-34.75,19.7-64.98,47.12-89.77,79.46-24.82,32.41-43.74,69.97-58.02,109.77-7.22,19.9-13.15,40.44-18.35,61.32l-3.68,15.75-3.28,15.89-3.14,15.99c-2.34,13.37-4.27-5.72-4.62-16.7Z"
        fill="#1ab7d1"
      />
      <path
        d="M922.46,330.55c.86,10.35,1.65,20.72,2.14,31.12,1.23,20.81,1.19,41.7,.44,62.66-1.75,41.88-7.37,84.19-19.75,125.55-12.21,41.26-31.57,81.7-59.3,116.49-13.72,17.46-29.51,33.28-46.44,47.55-17.03,14.18-35.39,26.53-54.36,37.43-19.06,10.8-38.88,19.76-58.94,27.65-10.03,4-20.23,7.31-30.39,10.74l-15.32,4.71c-5.03,1.57-10.71,3.08-16.05,4.29-21.66,5.07-43.48,8.01-65.46,8.76-21.96,.74-44.01-.54-65.72-4.41-43.33-7.44-85.59-25.6-118.6-54.31-16.49-14.26-30.84-30.66-42.15-48.7-2.71-4.6-5.55-9.06-8.08-13.7-2.4-4.72-4.98-9.3-7.18-14.06-2.05-4.85-4.2-9.62-6.12-14.46-1.81-4.9,.67-6.16,3.5-1.87,2.98,4.2,6.16,8.26,9.2,12.35,3.1,4.05,6.42,7.92,9.59,11.86,3.28,3.86,6.83,7.48,10.19,11.2,13.95,14.48,29.35,27.1,45.95,37.33,33.09,20.71,70.7,31.76,108.92,34.74,38.17,3.02,77.34-1.07,113.89-11.4,4.64-1.31,8.86-2.66,13.62-4.25l14.06-4.78c9.24-3.45,18.56-6.75,27.54-10.66,18.15-7.41,35.87-15.62,52.57-25.27,33.62-18.89,63.84-42.56,88.67-71.32,12.47-14.33,23.53-29.95,33.31-46.54,9.68-16.64,18.18-34.2,25.49-52.44,14.8-36.45,24.81-75.52,32.69-115.35,7.99-39.88,21.11-101.25,22.1-90.9Z"
        fill="#9d744f"
      />
      <path
        d="M733.6,626.97c-2.93,5.29-10.97,2.03-9.45-3.82,14.58-55.99,21.84-112.28,17.4-167.2-4.75-66.45-28.39-129.68-68.89-179.51-40.28-50.26-98.17-84.83-162.02-104.09-31.99-9.66-65.52-16.11-99.82-19.24-8.56-1.08-17.19-1.22-25.85-1.97-8.67-.88-17.35-.84-26.1-1.18-8.74-.25-17.55-.77-26.32-.41-8.81-.04-12.77-4.21-5.81-6.22,4.67-1.35,9.39-2.55,14.14-3.62,14.27-3.21,28.63-6.77,43.25-8.46,8.91-1.08,17.84-2.5,26.84-3.13,35.99-3.21,72.78-1.35,109.11,5.38,36.3,6.8,72.1,19.32,105.08,37.84,4.24,2.1,8.22,4.67,12.17,7.29l11.92,7.76c7.78,5.31,15.07,11.35,22.61,17.04,.11,.08,.22,.17,.32,.26,7.01,6.34,14.07,12.66,20.79,19.32l9.73,10.5c3.25,3.5,6.54,6.96,9.37,10.81,5.76,7.61,11.94,14.92,16.9,23.09l7.81,11.98c2.49,4.06,4.67,8.3,6.94,12.49,2.19,4.23,4.6,8.35,6.58,12.66l5.73,13.05c4.09,8.59,6.86,17.68,9.95,26.62,11.69,36,16.61,73.75,15.42,110.81-1.86,61.23-19.21,120.32-47.78,171.95Z"
        fill="#00966f"
      />
    </svg>
  )
}
