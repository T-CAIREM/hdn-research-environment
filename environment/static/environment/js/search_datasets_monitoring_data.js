function searchTable() {
    var input, filter, table, tr, td, i, j, txtValue;
    input = document.getElementById("searchInput");
    filter = input.value.toUpperCase();
    table = document.getElementById("monitoringTable");
    tr = table.getElementsByTagName("tr");
    for (i = 1; i < tr.length; i++) {
        tr[i].style.display = "none"; // Initially hide the row
        td = tr[i].getElementsByTagName("td");
        for (j = 0; j < 2; j++) { // Search only in dataset name and email
            if (td[j]) {
                txtValue = td[j].textContent || td[j].innerText;
                if (txtValue.toUpperCase().indexOf(filter) > -1) {
                    tr[i].style.display = ""; // Show the row
                    break; // No need to check other cells in this row
                }
            }
        }
    }
}
