$(function(){
    var current_region = $("#id_region").val()
    var current_instance_type = $("#id_instance_type").val()
    var current_instance_price = $(`#${current_region}-${current_instance_type}`)
    var current_data_price = $(`div[id*=${current_region}-Persistent]`)

    current_instance_price.show()
    current_data_price.show()
    $("#instance_total_cost").html(`<b>Total: ${current_instance_price.attr("data-cost")} $/hour</b>`)
    $("#data_total_cost").html(`<b>Total: ${current_data_price.attr("data-cost")} $/month</b>`)

    function change_instance_shown_pricing() {
        var current_region = $("#id_region").val()
        var current_instance_type = $("#id_instance_type").val()
        var current_instance_price = $(`#${current_region}-${current_instance_type}`)
        $("div.instance-costs").hide()
        current_instance_price.show()
    };

    function change_gpu_shown_pricing() {
        var current_gpu_accelerator = $("#id_gpu_accelerator").val()
        var current_region = $("#id_region").val()
        $("div.gpu-accelerator-costs").hide()

        if(current_gpu_accelerator){
            $("#gpu_accelerator_costs").show()
            $(`#${current_region}-${current_gpu_accelerator}`).show()
        };
    };

    function change_data_storage_costs_shown_pricing() {
        var current_region = $("#id_region").val()
        $("div.data-storage-costs").hide()
        $(`div[id*=${current_region}-Persistent]`).show()
        $("#data_total_cost").html(`<b>Total: ${current_data_price.attr("data-cost")} $/month</b>`)
    }

    $("#id_instance_type, #id_region, #id_gpu_accelerator").on("change", function(){
        var current_region = $("#id_region").val()
        var current_instance_type = $("#id_instance_type").val()
        var current_instance_price = $(`#${current_region}-${current_instance_type}`).attr("data-cost")
        var current_gpu_accelerator = $("#id_gpu_accelerator").val()
        var current_gpu_accelerator_price = $(`#${current_region}-${current_gpu_accelerator}`).attr("data-cost")
        var instance_total_cost = parseFloat(current_instance_price) + parseFloat(current_gpu_accelerator_price)

        if($("#id_gpu_accelerator").val()){
            $("#instance_total_cost").html(`<b>Total: ${ instance_total_cost.toPrecision(2) } $/hour</b>`)
        } else {
            $("#instance_total_cost").html(`<b>Total: ${current_instance_price } $/hour</b>`)
        }
    });

    $("#id_region").on("change", function(){
        change_instance_shown_pricing();
        change_gpu_shown_pricing();
        change_data_storage_costs_shown_pricing();
    });

    $("#id_instance_type").on("change", function(){
        change_instance_shown_pricing();
    });

    $("#id_gpu_accelerator").on("change", function(){
        change_gpu_shown_pricing()
    });

});
