// VALIDACIÓN BOOTSTRAP
(() => {
    'use strict';

    const form = document.getElementById('loginForm');

    form.addEventListener('submit', function (event) {

        if (!form.checkValidity()) {
            event.preventDefault();
            event.stopPropagation();
        }

        form.classList.add('was-validated');

    }, false);
})();