export async function fetchCatalog() {
  const response = await fetch('/api/catalog');
  return response.json();
}
