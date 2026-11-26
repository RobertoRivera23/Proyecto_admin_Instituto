// web/static/web/js/notificaciones.js
console.log('notificaciones.js cargado correctamente');

// Si había funciones que se llamaban, por ejemplo:
function alert_jqueryconfirm(mensaje) {
    if (typeof $.confirm !== 'undefined') {
        $.confirm({
            title: 'Notificación',
            content: mensaje,
            type: 'blue',
            buttons: {
                ok: {
                    text: 'Aceptar',
                    btnClass: 'btn-blue',
                    keys: ['enter'],
                    action: function(){}
                }
            }
        });
    } else {
        alert(mensaje);
    }
}