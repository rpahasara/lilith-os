// TEST-ONLY stand-in for `next/server` in the headless self-test bundle (esbuild cannot run the real
// module as ESM). Route handlers only need NextResponse as a standard Response; NextRequest is a type.
export class NextResponse extends Response {
  static json(body, init) {
    return Response.json(body, init);
  }
}
