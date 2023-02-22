$(function(){
    $("#id_region").on("change", function(){
        var current_region = $("#id_region").val()
        if (current_region != "us-central1") {
            $("#id_instance_type option[value=a2-highgpu-1g]").hide()
        } else {
            $("#id_instance_type option[value=a2-highgpu-1g]").show()
        }
    });
});
