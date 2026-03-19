import { PortalSectionIndexView } from '@/features/portal/views';

export default async function SectionPage({ params }: { params: Promise<{ section: string }> }) {
  const { section } = await params;
  return <PortalSectionIndexView section={section} />;
}
