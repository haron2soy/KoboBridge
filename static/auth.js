/*document.addEventListener("DOMContentLoaded", () => {
    const loginForm = document.getElementById("login-form");
    if (loginForm) {
        loginForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const email = document.getElementById("email").value;
            const password = document.getElementById("password").value;

            const response = await fetch("/api/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ email, password }),
            });

            const result = await response.json();
            const msgDiv = document.getElementById("login-msg");

            if (response.ok) {
                msgDiv.textContent = "Login successful! Redirecting...";
                setTimeout(() => window.location.href = "/", 1000);
            } else {
                msgDiv.textContent = result.error || "Login failed";
            }
        });
    }
});