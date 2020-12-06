function showText() {
    document.getElementById("message").style.display=("block");
    document.getElementById("message").style.color=("red");
  }

  function load() {
    document.getElementById("loading").style.display = ("block");
    document.getElementById("progress").style.width = "100%";
    setTimeout(showText, 5000);
  } 
  
  function blink() {
    let body = document.getElementById("message");
    if (body.style.color === "red")
    {
      body.style.color = "black";
    }
    else
    {
      body.style.color = "red";
    }
  }

  function support()
    {
        alert("Thank you for your support");
    }


  window.setInterval(blink, 500);
  
  


  
  