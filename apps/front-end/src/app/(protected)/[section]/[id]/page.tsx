import { PortalSectionDetailView } from '@/features/portal/views';

export default async function SectionDetailPage({ params }: { params: Promise<{ section: string; id: string }> }) {
  const { section, id } = await params;
  return <PortalSectionDetailView section={section} id={id} />;
}
