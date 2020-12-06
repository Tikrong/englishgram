/*Checks that the field is not empty and disables the submit button */

function not_empty(input1, input2, input3)
{
 if (document.getElementById(input1).value == "" || document.getElementById(input2).value == "" || document.getElementById(input3).value == "")
  {
     alert("You must fill the forms");
     event.preventDefault()
     return false;
  }

  return true;
}