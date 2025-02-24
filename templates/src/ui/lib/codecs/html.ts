function decode(input: string) {
  return new DOMParser().parseFromString(input, 'text/html').body.textContent || ''
}

export default { decode }
