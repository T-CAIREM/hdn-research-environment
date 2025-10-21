$(function(){
    var current_region = $("#id_workspace_region").val()
    var current_machine_type = $("#id_machine_type").val()
    var current_instance_price = $(`#${current_region}-${current_machine_type}`)
    var current_data_amount = $("#id_disk_size").val()
    var current_data_price = $(`div[id*=${current_region}-Persistent]`)

    current_instance_price.show()
    current_data_price.show()
    $("#instance_total_cost span").text(current_instance_price.attr("data-cost"))
    $("#data_total_cost span").text((parseInt(current_data_amount) * current_data_price.attr("data-cost")).toFixed(2))

    function change_instance_shown_pricing() {
        var current_machine_type = $("#id_machine_type").val()
        var current_instance_price = $(`#${current_region}-${current_machine_type}`)
        $("div.gpu-accelerator-costs").hide()
        $("#gpu_accelerator_costs").hide()
        $("div.instance-costs").hide()
        current_instance_price.show()
        $("#instance_total_cost span").text(current_instance_price.attr("data-cost") || "0")
    };

    function change_gpu_shown_pricing() {
        var current_gpu_accelerator = $("#id_gpu_accelerator").val()
        $("div.gpu-accelerator-costs").hide()

        if(current_gpu_accelerator){
            $("#gpu_accelerator_costs").show()
            $(`#${current_region}-${current_gpu_accelerator}`).show()
        };
    };

    function change_data_storage_costs_shown_pricing() {
        var current_data_amount = $("#id_disk_size").val()
        $("div.data-storage-costs").hide()
        $(`div[id*=${current_region}-Persistent]`).show()
        $("#data_total_cost span").text((parseInt(current_data_amount) * current_data_price.attr("data-cost")).toFixed(2))
    }

    $("#id_machine_type, #id_region, #id_gpu_accelerator").on("change", function(){
        var current_machine_type = $("#id_machine_type").val()
        var current_instance_price = current_machine_type ? $(`#${current_region}-${current_machine_type}`).attr("data-cost"): "0"
        var current_gpu_accelerator = $("#id_gpu_accelerator").val()
        var current_gpu_accelerator_price = current_gpu_accelerator ? $(`#${current_region}-${current_gpu_accelerator}`).attr("data-cost"): "0"
        var instance_total_cost = 0;

        $("div.instance-costs").hide();
        $("div.gpu-accelerator-costs").hide();

        if (current_machine_type) {
            $(`#${current_region}-${current_machine_type}`).show();
            instance_total_cost += parseFloat(current_instance_price);
        }
        if (current_gpu_accelerator) {
            $("#gpu_accelerator_costs").show();
            $(`#${current_region}-${current_gpu_accelerator}`).show();
            instance_total_cost += parseFloat(current_gpu_accelerator_price);
        }

        if (!current_machine_type && !current_gpu_accelerator) {
            $("#instance_total_cost span").text("0");
        } else {
            $("#instance_total_cost span").text(instance_total_cost.toFixed(2));
        }
    });

    $("#id_region").on("change", function(){
        change_instance_shown_pricing();
        change_gpu_shown_pricing();
        change_data_storage_costs_shown_pricing();
    });

    $("#id_machine_type").on("change", function(){
        change_instance_shown_pricing();
    });

    $("#id_gpu_accelerator").on("change", function(){
        change_gpu_shown_pricing();
    });

    $("#id_disk_size").on("change", function(){
        change_data_storage_costs_shown_pricing();
    });

});
