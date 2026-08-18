// Minimal test to verify resolveUserId logic works
const BACKEND_API_URL = "http://localhost:5000";
const BACKEND_API_KEY = "dev_api_access_key";

async function resolveUserId(githubLogin) {
  const res = await fetch(
    `${BACKEND_API_URL}/api/users/by-github/${encodeURIComponent(githubLogin)}`,
    { headers: { Authorization: `Bearer ${BACKEND_API_KEY}` } },
  );
  if (res.status === 404) return null;
  if (!res.ok) {
    throw new Error(`Could not resolve GitHub identity (${res.status}).`);
  }
  return await res.json();
}

// Test it
(async () => {
  try {
    console.log("Testing resolveUserId('saksham-gagneja-indxx')...");
    const result = await resolveUserId("saksham-gagneja-indxx");
    console.log("✅ Success:", JSON.stringify(result, null, 2));
  } catch (e) {
    console.error("❌ Error:", e.message);
  }
})();
