document.addEventListener("DOMContentLoaded", function() {
    const form = document.getElementById("insumoForm");

    if (form) {
        form.addEventListener("submit", function(event) {
            let isValid = true;

            // 1. Limpiar errores previos
            document.querySelectorAll('.input-error').forEach(el => el.classList.remove('input-error'));
            document.querySelectorAll('.invalid-feedback').forEach(el => {
                el.style.display = 'none';
                el.innerText = '';
            });

            // 2. Obtener los campos (Django autogenera los IDs como 'id_nombredelcampo')
            const nombre = document.getElementById("id_nombre");
            const stockMinimo = document.getElementById("id_stock_minimo");
            const stockActual = document.getElementById("id_stock_actual");

            // Validación: Nombre no puede estar vacío
            if (nombre && nombre.value.trim() === "") {
                showError("nombre", "El nombre del insumo es obligatorio.");
                isValid = false;
            }

            // Validación: Stock Mínimo no puede ser negativo
            if (stockMinimo && stockMinimo.value !== "") {
                const min = parseInt(stockMinimo.value);
                if (min < 0) {
                    showError("stock_minimo", "El stock mínimo no puede ser negativo.");
                    isValid = false;
                }
            }

            // Validación: Stock Actual no puede ser negativo
            if (stockActual && stockActual.value !== "") {
                const actual = parseInt(stockActual.value);
                if (actual < 0) {
                    showError("stock_actual", "El stock actual no puede ser menor a 0.");
                    isValid = false;
                }
            }

            // Si hay errores, detenemos el envío del formulario
            if (!isValid) {
                event.preventDefault();
            }
        });
    }

    // Función auxiliar para mostrar errores visualmente
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