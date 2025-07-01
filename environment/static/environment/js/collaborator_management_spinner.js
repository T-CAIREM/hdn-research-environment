$(function() {
    const addingText = "<i class='fas fa-spinner fa-pulse'></i> Adding...";
    const removingText = "<i class='fas fa-spinner fa-pulse'></i> Removing...";

    $("#add-collaborator-form").submit(function() {
        const button = $(this).find(":submit");
        const originalText = button.html();
        button.data('original-text', originalText);
        button.html(addingText);
        button.prop('disabled', true);
    });

    $(".remove-collaborator-btn").click(function() {
        const button = $(this);
        const originalText = button.html();
        button.data('original-text', originalText);
        button.html(removingText);
        button.prop('disabled', true);

        const form = button.closest('.modal-footer').find('form');
        form.submit();
    });
});
