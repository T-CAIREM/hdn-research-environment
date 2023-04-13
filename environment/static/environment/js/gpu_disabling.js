$(function(){
    var current_environment = $("#id_environment_type")
    var gpu_accelerator_dropdown = $("select#id_gpu_accelerator")
    var gpu_accelerator_label = $("label[for=id_gpu_accelerator]")
    current_environment.on("change", function(){
        if ($("input[value=rstudio]").is(":checked")) {
            gpu_accelerator_dropdown.hide()
            gpu_accelerator_label.hide()
        } else {
            gpu_accelerator_dropdown.show()
            gpu_accelerator_label.show()
        }
    });
});