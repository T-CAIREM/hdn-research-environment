$(function(){
    // Initialize pricing display on page load
    updateInstancePricing();
    updateDataStoragePricing();

    // Update pricing when selections change
    $("#id_region, #id_machine_type, #id_gpu_accelerator").on("change", function(){
        updateInstancePricing();
    });

    $("#id_region, #id_disk_size").on("change", function(){
        updateDataStoragePricing();
    });

    function updateInstancePricing() {
        var current_region = $("#id_region").val();
        var current_machine_type = $("#id_machine_type").val();
        var current_gpu_accelerator = $("#id_gpu_accelerator").val();

        // Hide all pricing displays
        $("div.instance-costs").hide();
        $("div.gpu-accelerator-costs").hide();
        $("#gpu_accelerator_costs").hide();

        var instance_total_cost = 0;

        // Show and calculate instance cost
        if (current_machine_type && current_region) {
            var instance_element = $(`#${current_region}-${current_machine_type}`);
            if (instance_element.length > 0) {
                instance_element.show();
                var instance_cost = parseFloat(instance_element.attr("data-cost")) || 0;
                instance_total_cost += instance_cost;
            }
        }

        // Show and calculate GPU cost
        if (current_gpu_accelerator && current_region) {
            var gpu_element = $(`#${current_region}-${current_gpu_accelerator}`);
            if (gpu_element.length > 0) {
                $("#gpu_accelerator_costs").show();
                gpu_element.show();
                var gpu_cost = parseFloat(gpu_element.attr("data-cost")) || 0;
                instance_total_cost += gpu_cost;
            }
        }

        // Update total display
        $("#instance_total_cost span").text(instance_total_cost.toFixed(2));
    }

    function updateDataStoragePricing() {
        var current_region = $("#id_region").val();
        var current_data_amount = parseInt($("#id_disk_size").val()) || 0;

        // Hide all data storage costs
        $("div.data-storage-costs").hide();

        var data_total_cost = 0;

        // Show and calculate data storage cost
        if (current_region) {
            var storage_element = $(`div[id*=${current_region}-Persistent]`);
            if (storage_element.length > 0) {
                storage_element.show();
                var storage_cost_per_gb = parseFloat(storage_element.attr("data-cost")) || 0;
                data_total_cost = current_data_amount * storage_cost_per_gb;
            }
        }

        // Update total display
        $("#data_total_cost span").text(data_total_cost.toFixed(2));
    }
});
