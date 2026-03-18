import { SectionIndexView } from '@/features/admin/views';

export default async function SectionPage({ params }: { params: Promise<{ section: string }> }) {
  const { section } = await params;
  return <SectionIndexView section={section} />;
}
