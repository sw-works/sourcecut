import { SharedBoardView } from "../../../../components/odyssey/shared-board-view";

export default async function SharedBoardPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return <main id="odyssey-main"><SharedBoardView token={token} /></main>;
}
