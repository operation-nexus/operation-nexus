# Elevation Budgeting & Z-Fighting Immunity

## 1. Physical Elevation Budget

In 3D WebGL scenes, coplanar polygons flicker violently (Z-fighting). All meshes must adhere to the vertical budget:

| Layer | Elevation ($Y$) | Material / Mesh Details |
| :--- | :--- | :--- |
| **Overhead Signage / Glyphs** | $+2.50\text{ m}$ | Floating holographic text billboards |
| **Elevated Bridges** | $+2.00\text{ m}$ | Engineered causeway spanning water channel |
| **Convoy Suspension** | $+0.35\text{ m}$ | Wheels contact road surface |
| **Road Ribbons (MSR)** | $+0.22\text{ m}$ | Tarmac mesh with `polygonOffset: true` (`factor: -1, units: -2`) |
| **Ground Landmass** | $+0.00\text{ m}$ | Lowland terrain mesh with quad subdivisions |
| **Shoreline Bevel** | $-1.50\text{ m}$ | Coastal transition |
| **Water Surface** | $-3.50\text{ m}$ | Recessed channel plane |
| **Channel Trench Bed** | $-7.50\text{ m}$ | Submarine trench floor |

## 2. Geometric Channel Separation

Never place an overlapping water plane across land. Split landmasses into physical West and East polygons separated by an explicit channel (e.g. 70m gap for Strait-1) so triangles never overlap.

## 3. WebGL Depth Buffer Configuration
```javascript
const renderer = new THREE.WebGLRenderer({
  antialias: true,
  logarithmicDepthBuffer: true // Crucial for wide-area 400km terrain maps
});
```
