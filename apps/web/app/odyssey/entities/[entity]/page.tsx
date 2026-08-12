import EntityDirectory from "../../../../components/odyssey/entity-directory";
export default async function EntityPage({
  params,
}: {
  params: Promise<{ entity: string }>;
}) {
  const { entity } = await params;
  return (
    <main id="odyssey-main">
      <EntityDirectory initialId={entity} />
    </main>
  );
}
