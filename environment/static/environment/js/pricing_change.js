$(function(){
    var current_region = $("#id_region").val()
    var current_instance_type = $("#id_instance_type").val()
    $(`#${current_region}-${current_instance_type}`).show()
    $(`#${current_region}-Persistent data disk 1GB`).show()
    $(`div[id*=${current_region}-Persistent]`).show()

    function change_instance_shown_pricing() {
        var current_region = $("#id_region").val()
        var current_instance_type = $("#id_instance_type").val()
        $("div.instance-costs").hide()
        $(`#${current_region}-${current_instance_type}`).show()
    };

    function change_gpu_shown_pricing() {
        if($("#id_gpu_accelerated").is(":checked")){
            var current_region = $("#id_region").val()
            $("div.gpu-accelerator-costs").hide()
            $("#gpu_accelerator_costs").show()
            $(`#${current_region}-gpu`).show()
        };
    };

    function change_additional_costs_shown_pricing() {
        var current_region = $("#id_region").val()
        $("div.additional-costs").hide()
        $(`div[id*=${current_region}-Persistent]`).show()
    }

    $("#id_region").on("change", function(){
        change_instance_shown_pricing();
        change_gpu_shown_pricing();
        change_additional_costs_shown_pricing();
    });

    $("#id_instance_type").on("change", function(){
        change_instance_shown_pricing();
    });

    $("#id_gpu_accelerated").on("change", function(){
        var current_region = $("#id_region").val()

        if($("#id_gpu_accelerated").is(":checked")){
            $("#gpu_accelerator_costs").show()
            $(`#${current_region}-gpu`).show()
        } else {
            $("#gpu_accelerator_costs").hide()
            $("div.gpu-accelerator-costs").hide()
        }
    });

});
