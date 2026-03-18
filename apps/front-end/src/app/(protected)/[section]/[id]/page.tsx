import { SectionDetailView } from '@/features/admin/views';

export default async function SectionDetailPage({ params }: { params: Promise<{ section: string; id: string }> }) {
  const { section, id } = await params;
  return <SectionDetailView section={section} id={id} />;
}
