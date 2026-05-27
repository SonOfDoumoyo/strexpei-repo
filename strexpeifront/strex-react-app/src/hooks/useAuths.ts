// authStore.ts

export function setAccessToken(uid: string,token: string) {

    sessionStorage.setItem(uid, token);
}

export function getAccessToken(uid: string){
    return sessionStorage.getItem(uid);
}

export function clearAccessToken(uid: string): void {
    sessionStorage.removeItem(uid);
}
