document.addEventListener("DOMContentLoaded", function() {
    const form = document.getElementById("addInsumoForm");

    if (form) {
        form.addEventListener("submit", function(event) {
            let isValid = true;

            // Limpiar errores previos
            document.querySelectorAll('.input-error').forEach(el => el.classList.remove('input-error'));
            document.querySelectorAll('.invalid-feedback').forEach(el => {
                el.style.display = 'none';
                el.innerText = '';
            });

            // Capturar campos
            const insumo = document.getElementById("id_insumo");
            const cantidad = document.getElementById("id_cantidad");
            const precio = document.getElementById("id_precio");

            // Validar Insumo (Debe estar seleccionado)
            if (insumo && insumo.value === "") {
                showError("insumo", "Debes seleccionar un insumo de la lista.");
                isValid = false;
            }

            // Validar Cantidad (Debe ser mayor a 0)
            if (cantidad) {
                if (cantidad.value.trim() === "") {
                    showError("cantidad", "Ingresa una cantidad.");
                    isValid = false;
                } else if (parseInt(cantidad.value) <= 0) {
                    showError("cantidad", "La cantidad debe ser mayor a 0.");
                    isValid = false;
                }
            }

            // Validar Precio (Debe ser mayor o igual a 0)
            if (precio) {
                if (precio.value.trim() === "") {
                    showError("precio", "Ingresa el precio unitario.");
                    isValid = false;
                } else if (parseFloat(precio.value) < 0) {
                    showError("precio", "El precio no puede ser negativo.");
                    isValid = false;
                }
            }

            // Prevenir envío si hay errores
            if (!isValid) {
                event.preventDefault();
            }
        });
    }

    // Función para mostrar los errores en pantalla
    function showError(fieldName, message) {
        const inputField = document.getElementById("id_" + fieldName);
        const errorDiv = document.getElementById("error-" + fieldName);
        
        if (inputField && errorDiv) {
            inputField.classList.add("input-error");
            errorDiv.innerText = message;
            errorDiv.style.display = "block";
        }
    }
});