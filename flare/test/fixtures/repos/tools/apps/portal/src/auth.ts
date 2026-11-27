export const routes = { signIn: '/login' };
export async function passkey() { return navigator.credentials.get({ publicKey: {} as never }); }
