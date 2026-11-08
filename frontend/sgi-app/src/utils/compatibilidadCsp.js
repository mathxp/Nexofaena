// La política de seguridad (CSP, ver public/_headers) prohíbe ejecutar texto
// como código (eval / new Function). exceljs trae un runtime antiguo que hace
//   try { regeneratorRuntime = r } catch { Function("r", "regeneratorRuntime = r")(r) }
// En un módulo estricto la asignación falla si la variable global no existe y
// cae al Function(), que la CSP bloquea y rompe el Dashboard y las
// exportaciones a Excel. Declarándola antes, la asignación normal funciona.
if (!('regeneratorRuntime' in globalThis)) {
  globalThis.regeneratorRuntime = undefined;
}
