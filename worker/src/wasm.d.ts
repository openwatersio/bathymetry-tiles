declare module "*.wasm" {
  const wasm: WebAssembly.Module;
  export default wasm;
}

// jSquash's decode/encode types reference the DOM `ImageData`, which the Workers
// runtime (lib: esnext, no DOM) doesn't provide. We only ever touch {data,width,height},
// so a minimal global declaration covers the casts and decode's return shape.
interface ImageData {
  data: Uint8ClampedArray;
  width: number;
  height: number;
}
