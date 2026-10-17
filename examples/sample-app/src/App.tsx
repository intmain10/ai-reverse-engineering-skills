import React from 'react';
import { fetchCatalog } from './api';
export function App() {
  return <main><h1>Example Shop</h1><button onClick={fetchCatalog}>Load</button></main>;
}
