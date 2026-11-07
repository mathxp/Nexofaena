// Todo el sistema trabaja con números enteros: el pañol entrega unidades,
// pares o cajas completas, y los pesos chilenos no llevan decimales.

// Bloquea en los <input type="number"> las teclas que permitirían escribir un
// decimal, un exponente o un signo (".", ",", "e", "+", "-").
export const soloEnteros = (evento) => {
  if (['.', ',', 'e', 'E', '+', '-'].includes(evento.key)) evento.preventDefault();
};

// Props comunes para un campo de cantidad entera.
export const PROPS_ENTERO = { step: '1', inputMode: 'numeric', onKeyDown: soloEnteros };


// "42.00" -> 42 al mostrar una cantidad o un stock. Si no es un número, lo
// deja tal cual (ej. "-" o vacío).
export const entero = (valor) => {
  if (valor === null || valor === undefined || valor === '') return valor;
  const numero = Number(valor);
  return Number.isFinite(numero) ? Math.round(numero) : valor;
};
