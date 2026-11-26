$(document).ready(function() {
    // Autocomplete para clientes
    $('.cliente-autocomplete').select2({
        ajax: {
            url: '/facturacion/api/buscar-cliente/',
            dataType: 'json',
            delay: 250,
            data: function(params) {
                return { q: params.term };
            },
            processResults: function(data) {
                return {
                    results: data.results
                };
            },
            cache: true
        },
        minimumInputLength: 3
    });
    
    // Autocomplete para productos
    $('.producto-autocomplete').select2({
        ajax: {
            url: '/facturacion/api/buscar-producto/',
            dataType: 'json',
            delay: 250,
            data: function(params) {
                return { q: params.term };
            },
            processResults: function(data) {
                return {
                    results: data.results
                };
            },
            cache: true
        },
        minimumInputLength: 1
    });
    
    // Calcular totales en tiempo real
    $('.item-cantidad, .item-precio, .item-descuento, .item-iva').on('change', function() {
        calcularTotalesItem($(this).closest('tr'));
    });
    
    function calcularTotalesItem(row) {
        const cantidad = parseFloat(row.find('.item-cantidad').val()) || 0;
        const precio = parseFloat(row.find('.item-precio').val()) || 0;
        const descuento = parseFloat(row.find('.item-descuento').val()) || 0;
        const ivaPorcentaje = parseFloat(row.find('.item-iva').val()) || 0;
        
        const subtotal = (cantidad * precio) - descuento;
        const iva = subtotal * (ivaPorcentaje / 100);
        const total = subtotal + iva;
        
        // Actualizar campos ocultos o mostrar en UI
        row.find('.item-subtotal').val(subtotal.toFixed(2));
        row.find('.item-total').val(total.toFixed(2));
        
        calcularTotalesGenerales();
    }
    
    function calcularTotalesGenerales() {
        let subtotal = 0;
        let iva = 0;
        
        $('tr.item-row').each(function() {
            subtotal += parseFloat($(this).find('.item-subtotal').val()) || 0;
            iva += parseFloat($(this).find('.item-iva-monto').val()) || 0;
        });
        
        $('#id_subtotal').val(subtotal.toFixed(2));
        $('#id_iva').val(iva.toFixed(2));
        $('#id_total').val((subtotal + iva).toFixed(2));
    }
});